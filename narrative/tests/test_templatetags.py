"""
Tests for narrative template tags and filters.
"""
from django.test import TestCase, RequestFactory, override_settings
from django.template import Template, Context

from narrative.templatetags.narrative_tags import (
    md, replace, connection_class, connection_color, truncate_title,
    tier_icon, tier_class, tier_label, tier_color,
    connection_icon, page_type_icon, page_type_color,
)


# =============================================================================
# FILTER TESTS
# =============================================================================

class MdFilterTest(TestCase):
    """Tests for the |md inline markdown filter."""

    def test_empty_value(self):
        self.assertEqual(md(''), '')

    def test_none_value(self):
        self.assertEqual(md(None), '')

    def test_plain_text_passthrough(self):
        self.assertEqual(md('hello world'), 'hello world')

    def test_bold_conversion(self):
        result = md('this is **bold** text')
        self.assertIn('<strong>bold</strong>', result)

    def test_italic_conversion(self):
        result = md('this is *italic* text')
        self.assertIn('<em>italic</em>', result)

    def test_bold_and_italic_together(self):
        result = md('**bold** and *italic*')
        self.assertIn('<strong>bold</strong>', result)
        self.assertIn('<em>italic</em>', result)

    def test_strip_wrapping_bold(self):
        """LLM output often wraps entire title in **bold**."""
        result = md('**My Title**')
        # After stripping wrapping ** and then escaping, should be plain text
        self.assertEqual(result, 'My Title')

    def test_strip_wrapping_quotes(self):
        """LLM output sometimes wraps text in quotes."""
        result = md('"My Title"')
        self.assertEqual(result, 'My Title')

    def test_strip_smart_quotes(self):
        result = md('\u201cMy Title\u201d')
        self.assertEqual(result, 'My Title')

    def test_strip_bold_wrapping_with_quotes(self):
        """Handles nested **"title"** pattern."""
        result = md('**"My Title"**')
        self.assertEqual(result, 'My Title')

    def test_html_escaping(self):
        """Ensures HTML is escaped for safety."""
        result = md('<script>alert("xss")</script>')
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)

    def test_mark_safe_output(self):
        """Result should be marked safe for template rendering."""
        result = md('**bold**')
        self.assertTrue(hasattr(result, '__html__'))

    def test_integer_input(self):
        """Should handle non-string input by converting to str."""
        result = md(42)
        self.assertEqual(result, '42')

    def test_whitespace_stripping(self):
        result = md('  hello  ')
        self.assertEqual(result, 'hello')


class ReplaceFilterTest(TestCase):
    """Tests for the |replace filter."""

    def test_basic_replace(self):
        self.assertEqual(replace('hello world', 'world:universe'), 'hello universe')

    def test_empty_value(self):
        self.assertIsNone(replace(None, 'a:b'))

    def test_empty_string(self):
        self.assertEqual(replace('', 'a:b'), '')

    def test_no_match(self):
        self.assertEqual(replace('hello', 'xyz:abc'), 'hello')

    def test_invalid_args_no_colon(self):
        """Returns original value when args can't be split."""
        self.assertEqual(replace('hello', 'nocolon'), 'hello')

    def test_replace_underscore_with_space(self):
        self.assertEqual(replace('hello_world', '_: '), 'hello world')


class ConnectionClassFilterTest(TestCase):
    """Tests for |connection_class filter."""

    def test_causal(self):
        self.assertEqual(connection_class('CAUSAL'), 'conn-causal')

    def test_thematic_parallel(self):
        self.assertEqual(connection_class('THEMATIC_PARALLEL'), 'conn-thematic-parallel')

    def test_character_continuity(self):
        self.assertEqual(connection_class('CHARACTER_CONTINUITY'), 'conn-character-continuity')

    def test_foreshadowing(self):
        self.assertEqual(connection_class('FORESHADOWING'), 'conn-foreshadowing')


class ConnectionColorFilterTest(TestCase):
    """Tests for |connection_color filter."""

    def test_known_types(self):
        self.assertEqual(connection_color('CAUSAL'), '#22d3ee')
        self.assertEqual(connection_color('FORESHADOWING'), '#a855f7')
        self.assertEqual(connection_color('THEMATIC_PARALLEL'), '#f59e0b')
        self.assertEqual(connection_color('ESCALATION'), '#ef4444')
        self.assertEqual(connection_color('EMOTIONAL_ECHO'), '#ec4899')

    def test_unknown_type_returns_default(self):
        self.assertEqual(connection_color('UNKNOWN'), '#64748b')


class TruncateTitleFilterTest(TestCase):
    """Tests for |truncate_title filter."""

    def test_short_title_unchanged(self):
        self.assertEqual(truncate_title('Short'), 'Short')

    def test_exact_length_unchanged(self):
        title = 'x' * 30
        self.assertEqual(truncate_title(title), title)

    def test_long_title_truncated(self):
        result = truncate_title('This is a very long title that should be truncated', 20)
        self.assertTrue(result.endswith('...'))
        self.assertTrue(len(result) <= 24)  # 20 chars + some word boundary + ...

    def test_truncates_at_word_boundary(self):
        result = truncate_title('Hello World Foo Bar', 12)
        # Should truncate at word boundary before length 12
        self.assertTrue(result.endswith('...'))
        self.assertNotIn('Fo', result)  # Should not split "Foo" mid-word

    def test_custom_length(self):
        result = truncate_title('Short', 10)
        self.assertEqual(result, 'Short')


class TierFilterTests(TestCase):
    """Tests for tier_icon, tier_class, tier_label, tier_color filters."""

    def test_tier_icon_anchor(self):
        self.assertEqual(tier_icon('anchor'), '\u2600\ufe0f')

    def test_tier_icon_planet(self):
        self.assertEqual(tier_icon('planet'), '\U0001fa90')

    def test_tier_icon_asteroid(self):
        self.assertEqual(tier_icon('asteroid'), '\u2604\ufe0f')

    def test_tier_icon_unknown(self):
        self.assertEqual(tier_icon('unknown'), '\u2604\ufe0f')

    def test_tier_class_known(self):
        self.assertEqual(tier_class('anchor'), 'tier-anchor')
        self.assertEqual(tier_class('planet'), 'tier-planet')

    def test_tier_class_empty(self):
        self.assertEqual(tier_class(''), 'tier-asteroid')

    def test_tier_class_none(self):
        self.assertEqual(tier_class(None), 'tier-asteroid')

    def test_tier_label_known(self):
        self.assertEqual(tier_label('anchor'), 'Main Cast')
        self.assertEqual(tier_label('planet'), 'Recurring')
        self.assertEqual(tier_label('asteroid'), 'One-off')

    def test_tier_label_unknown(self):
        self.assertEqual(tier_label('unknown'), 'One-off')

    def test_tier_color_known(self):
        self.assertEqual(tier_color('anchor'), '#fbbf24')
        self.assertEqual(tier_color('planet'), '#14b8a6')
        self.assertEqual(tier_color('asteroid'), '#6b7280')

    def test_tier_color_unknown(self):
        self.assertEqual(tier_color('unknown'), '#6b7280')


# =============================================================================
# SIMPLE TAG TESTS
# =============================================================================

class ConnectionIconTagTest(TestCase):
    """Tests for {% connection_icon %} tag."""

    def test_known_types(self):
        self.assertEqual(connection_icon('CAUSAL'), 'arrow-right')
        self.assertEqual(connection_icon('FORESHADOWING'), 'sparkles')
        self.assertEqual(connection_icon('THEMATIC_PARALLEL'), 'git-merge')
        self.assertEqual(connection_icon('CHARACTER_CONTINUITY'), 'rotate-ccw')
        self.assertEqual(connection_icon('ESCALATION'), 'trending-up')
        self.assertEqual(connection_icon('CALLBACK'), 'arrow-left')
        self.assertEqual(connection_icon('EMOTIONAL_ECHO'), 'heart')
        self.assertEqual(connection_icon('SYMBOLIC_PARALLEL'), 'equal')
        self.assertEqual(connection_icon('TEMPORAL'), 'clock')

    def test_unknown_type(self):
        self.assertEqual(connection_icon('UNKNOWN'), 'link')


class PageTypeIconTagTest(TestCase):
    """Tests for {% page_type_icon %} tag."""

    def test_with_specific_class_name(self):
        """Test with an object that has specific_class_name."""
        class MockPage:
            specific_class_name = 'EventPage'
        self.assertEqual(page_type_icon(MockPage()), 'zap')

    def test_with_class_name(self):
        """Test with an object that uses __class__.__name__."""
        class CharacterPage:
            pass
        self.assertEqual(page_type_icon(CharacterPage()), 'user')

    def test_unknown_page_type(self):
        class UnknownPage:
            pass
        self.assertEqual(page_type_icon(UnknownPage()), 'file-text')

    def test_all_known_types(self):
        types = {
            'EventPage': 'zap',
            'CharacterPage': 'user',
            'EpisodePage': 'film',
            'SeasonPage': 'folder',
            'SeriesIndexPage': 'tv',
            'OrganizationPage': 'building-2',
        }
        for class_name, expected_icon in types.items():
            class MockPage:
                specific_class_name = class_name
            self.assertEqual(page_type_icon(MockPage()), expected_icon)


class PageTypeColorTagTest(TestCase):
    """Tests for {% page_type_color %} tag."""

    def test_event_page(self):
        class MockPage:
            specific_class_name = 'EventPage'
        self.assertEqual(page_type_color(MockPage()), 'amber')

    def test_character_page(self):
        class MockPage:
            specific_class_name = 'CharacterPage'
        self.assertEqual(page_type_color(MockPage()), 'emerald')

    def test_unknown_type(self):
        class MockPage:
            specific_class_name = 'UnknownPage'
        self.assertEqual(page_type_color(MockPage()), 'slate')


# =============================================================================
# TEMPLATE RENDERING INTEGRATION TESTS
# =============================================================================

class TemplateRenderingTest(TestCase):
    """Test that filters work correctly when used in Django templates."""

    def test_md_filter_in_template(self):
        template = Template('{% load narrative_tags %}{{ value|md }}')
        # Use inline bold that won't be stripped as wrapping bold
        result = template.render(Context({'value': 'text with **bold** inside'}))
        self.assertIn('<strong>bold</strong>', result)

    def test_connection_class_in_template(self):
        template = Template('{% load narrative_tags %}{{ ct|connection_class }}')
        result = template.render(Context({'ct': 'CAUSAL'}))
        self.assertEqual(result.strip(), 'conn-causal')

    def test_connection_color_in_template(self):
        template = Template('{% load narrative_tags %}{{ ct|connection_color }}')
        result = template.render(Context({'ct': 'ESCALATION'}))
        self.assertEqual(result.strip(), '#ef4444')

    def test_tier_label_in_template(self):
        template = Template('{% load narrative_tags %}{{ tier|tier_label }}')
        result = template.render(Context({'tier': 'anchor'}))
        self.assertEqual(result.strip(), 'Main Cast')

    def test_connection_icon_tag_in_template(self):
        template = Template('{% load narrative_tags %}{% connection_icon "CAUSAL" %}')
        result = template.render(Context({}))
        self.assertEqual(result.strip(), 'arrow-right')

    def test_replace_filter_in_template(self):
        template = Template('{% load narrative_tags %}{{ value|replace:"_: " }}')
        result = template.render(Context({'value': 'hello_world'}))
        self.assertEqual(result.strip(), 'hello world')
