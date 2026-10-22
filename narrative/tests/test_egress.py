"""
Origin-egress and session-bloat fixes (Railway bill investigation, Oct 2026).

- GZipMiddleware compresses HTML at the origin (Railway bills pre-edge bytes).
- ?theme= toggles set a cookie and 302 instead of writing a DB session.
- Detail pages render per theme from the cookie (no shared page cache).
- robots.txt fences off per-entity graph views, theme toggles, SEO crawlers.
- AgentMiss logging is capped per user agent per day.
- prune_sessions deletes expired sessions in batches.
"""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fabula_web import urls as project_urls
from narrative.models import AgentMiss
from narrative.tests.test_views import ViewTestMixin


class GzipTest(ViewTestMixin, TestCase):

    def test_html_is_gzipped_when_accepted(self):
        response = self.client.get(reverse('catalog'), HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Encoding'], 'gzip')

    def test_not_gzipped_without_accept_encoding(self):
        response = self.client.get(reverse('catalog'))
        self.assertFalse(response.has_header('Content-Encoding'))


class ThemeCookieTest(ViewTestMixin, TestCase):

    def test_toggle_sets_cookie_and_redirects_to_clean_url(self):
        response = self.client.get('/explore/?theme=dark')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/explore/')
        self.assertEqual(response.cookies['fabula_theme'].value, 'dark')

    def test_toggle_preserves_other_query_params(self):
        response = self.client.get('/explore/?season=2&theme=writerly')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/explore/?season=2')

    def test_unknown_theme_value_is_ignored(self):
        response = self.client.get('/explore/?theme=neon')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('fabula_theme', response.cookies)

    def test_toggle_and_page_views_create_no_sessions(self):
        self.client.get('/explore/?theme=dark', follow=True)
        self.client.get(reverse('catalog'))
        self.assertEqual(Session.objects.count(), 0)

    def test_cookie_selects_theme(self):
        self.client.cookies['fabula_theme'] = 'dark'
        response = self.client.get(
            reverse('character_detail', kwargs={'identifier': 'agent_001'}))
        self.assertContains(response, 'data-theme="dark"')

    def test_html_varies_on_cookie(self):
        response = self.client.get(reverse('catalog'))
        self.assertIn('Cookie', response['Vary'])

    def test_robots_does_not_vary_on_cookie(self):
        response = self.client.get('/robots.txt')
        self.assertNotIn('Cookie', response.get('Vary', ''))


class ThemeRenderTest(ViewTestMixin, TestCase):
    """One theme's render must never be served to the other."""

    def _theme_of(self, theme):
        self.client.cookies['fabula_theme'] = theme
        response = self.client.get(
            reverse('character_detail', kwargs={'identifier': 'agent_001'}))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_dark_render_is_not_served_to_writerly(self):
        self.assertIn('data-theme="dark"', self._theme_of('dark'))
        self.assertIn('data-theme="writerly"', self._theme_of('writerly'))
        self.assertIn('data-theme="dark"', self._theme_of('dark'))


class RobotsTxtTest(TestCase):

    def test_rules(self):
        body = self.client.get('/robots.txt').content.decode()
        for rule in (
            'Allow: /explore/*/graph/$',
            'Disallow: /explore/*/graph/',
            'Disallow: /graph/',
            'Disallow: /*?theme=',
            'User-agent: SemrushBot',
            'User-agent: AhrefsBot',
        ):
            self.assertIn(rule, body)
        # SEO crawlers share one group that disallows everything
        seo_group = body.split('User-agent: SemrushBot', 1)[1]
        self.assertIn('Disallow: /\n', seo_group)


class AgentMissCapTest(TestCase):

    def setUp(self):
        cache.clear()
        project_urls._agent_miss_counts.clear()

    def test_misses_are_capped_per_user_agent(self):
        with mock.patch.object(project_urls, 'AGENT_MISS_DAILY_CAP', 3):
            for i in range(6):
                response = self.client.get(
                    f'/no-such-page-{i}/', HTTP_USER_AGENT='GPTBot/1.0')
                self.assertEqual(response.status_code, 404)
            self.client.get('/no-such-page/', HTTP_USER_AGENT='ClaudeBot/1.0')
        self.assertEqual(AgentMiss.objects.filter(user_agent='GPTBot/1.0').count(), 3)
        self.assertEqual(AgentMiss.objects.filter(user_agent='ClaudeBot/1.0').count(), 1)

    def test_capped_agents_still_get_the_markdown_404(self):
        with mock.patch.object(project_urls, 'AGENT_MISS_DAILY_CAP', 0):
            response = self.client.get('/no-such-page/', HTTP_USER_AGENT='GPTBot/1.0')
        self.assertEqual(response['Content-Type'], 'text/markdown; charset=utf-8')
        self.assertEqual(AgentMiss.objects.count(), 0)


class PruneAgentMissesTest(TestCase):

    def _make(self, n, age_days):
        rows = AgentMiss.objects.bulk_create(
            AgentMiss(path=f'/x-{age_days}-{i}/', user_agent='GPTBot/1.0')
            for i in range(n)
        )
        # created_at is auto_now_add, so backdate after insert
        AgentMiss.objects.filter(pk__in=[r.pk for r in rows]).update(
            created_at=timezone.now() - timedelta(days=age_days))

    def test_deletes_only_rows_older_than_window(self):
        self._make(5, age_days=45)
        self._make(3, age_days=2)
        out = StringIO()
        call_command('prune_agent_misses', '--batch-size', '2', stdout=out)
        self.assertEqual(AgentMiss.objects.count(), 3)
        self.assertIn('Deleted 5 agent misses older than 30 days', out.getvalue())

    def test_days_option(self):
        self._make(2, age_days=45)
        call_command('prune_agent_misses', '--days', '60', stdout=StringIO())
        self.assertEqual(AgentMiss.objects.count(), 2)

    def test_dry_run_deletes_nothing(self):
        self._make(4, age_days=45)
        out = StringIO()
        call_command('prune_agent_misses', '--dry-run', stdout=out)
        self.assertEqual(AgentMiss.objects.count(), 4)
        self.assertIn('4 of 4 agent misses are older than 30 days', out.getvalue())


class PruneSessionsTest(TestCase):

    def _make(self, n, expire_date):
        Session.objects.bulk_create(
            Session(session_key=f'k{expire_date:%s}{i}', session_data='x',
                    expire_date=expire_date)
            for i in range(n)
        )

    def test_deletes_only_expired_in_batches(self):
        now = timezone.now()
        self._make(7, now - timedelta(days=1))
        self._make(2, now + timedelta(days=1))
        out = StringIO()
        call_command('prune_sessions', '--batch-size', '3', stdout=out)
        self.assertEqual(Session.objects.count(), 2)
        self.assertIn('Deleted 7 expired sessions', out.getvalue())

    def test_dry_run_deletes_nothing(self):
        self._make(4, timezone.now() - timedelta(days=1))
        out = StringIO()
        call_command('prune_sessions', '--dry-run', stdout=out)
        self.assertEqual(Session.objects.count(), 4)
        self.assertIn('4 expired of 4 sessions', out.getvalue())
