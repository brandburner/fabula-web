import json

from django.core.cache import cache
from django.test import override_settings

from .base import NarrativeGraphTestCase


def parse_sse(body):
    events = []
    for chunk in body.split('\n\n'):
        name, data = None, None
        for line in chunk.split('\n'):
            if line.startswith('event:'):
                name = line[6:].strip()
            elif line.startswith('data:'):
                data = line[5:].strip()
        if data == '[DONE]':
            events.append(('done', None))
        elif name and data:
            events.append((name, json.loads(data)))
    return events


@override_settings(CHAT_ENABLED=True, CHAT_LLM_BACKEND='fake')
class ChatStreamTests(NarrativeGraphTestCase):
    def setUp(self):
        cache.clear()

    def post(self, payload):
        return self.client.post(
            '/api/chat/', data=json.dumps(payload),
            content_type='application/json')

    def test_full_sse_turn(self):
        resp = self.post({'message': 'What is in the archive?',
                          'series': 'alpha-show'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/event-stream')
        events = parse_sse(b''.join(resp.streaming_content).decode())
        names = [n for n, _ in events]
        self.assertIn('tool_start', names)
        self.assertIn('content', names)
        self.assertIn('rich_links', names)
        self.assertIn('metadata', names)
        self.assertEqual(names[-1], 'done')

        metadata = dict(events)['metadata']
        self.assertEqual(metadata['series'], 'alpha-show')
        self.assertFalse(metadata['fallback'])
        self.assertTrue(metadata['tool_context'])

        links = dict(events)['rich_links']['links']
        self.assertTrue(
            any(l['url'] == '/explore/alpha-show/' for l in links))

    def test_bad_series_falls_back_to_first_live(self):
        resp = self.post({'message': 'hello', 'series': 'not-real'})
        events = parse_sse(b''.join(resp.streaming_content).decode())
        self.assertIn(dict(events)['metadata']['series'],
                      ('alpha-show', 'beta-show'))

    def test_empty_message_rejected(self):
        resp = self.post({'message': '   ', 'series': 'alpha-show'})
        self.assertEqual(resp.status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get('/api/chat/').status_code, 405)

    @override_settings(CHAT_RATE_LIMIT_PER_MINUTE=2)
    def test_rate_limited(self):
        for _ in range(2):
            resp = self.post({'message': 'hi', 'series': 'alpha-show'})
            b''.join(resp.streaming_content)
            self.assertEqual(resp.status_code, 200)
        resp = self.post({'message': 'hi', 'series': 'alpha-show'})
        self.assertEqual(resp.status_code, 429)
        self.assertIn('Retry-After', resp)

    def test_hostile_tool_context_ignored(self):
        resp = self.post({
            'message': 'hi', 'series': 'alpha-show',
            'tool_context': [
                {'tool': 'drop_tables', 'digest': {'name': 'x'}},
                {'tool': 'graph_stats',
                 'digest': {'evil_key': 'x', 'name': 'ok'}},
                'garbage',
            ]})
        self.assertEqual(resp.status_code, 200)
        b''.join(resp.streaming_content)


@override_settings(CHAT_ENABLED=False)
class ChatDisabledTests(NarrativeGraphTestCase):
    def test_stream_disabled(self):
        resp = self.client.post(
            '/api/chat/', data=json.dumps({'message': 'hi'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 503)

    def test_suggestions_empty(self):
        resp = self.client.get('/api/chat/suggestions/')
        self.assertEqual(resp.json(), {'chips': []})


@override_settings(CHAT_ENABLED=True, CHAT_LLM_BACKEND='fake')
class SuggestionTests(NarrativeGraphTestCase):
    def test_character_chips_are_entity_aware(self):
        resp = self.client.get(
            '/api/chat/suggestions/',
            {'page_type': 'character', 'entity_name': 'Alice Alpha'})
        labels = [c['label'] for c in resp.json()['chips']]
        self.assertTrue(any('Alice Alpha' in l for l in labels))

    def test_unknown_page_type_gets_generic_chips(self):
        resp = self.client.get('/api/chat/suggestions/',
                               {'page_type': 'weird'})
        self.assertTrue(resp.json()['chips'])


@override_settings(CHAT_ENABLED=True, CHAT_LLM_BACKEND='fake')
class WidgetRenderTests(NarrativeGraphTestCase):
    def setUp(self):
        # CharacterDetailView sits behind cache_page(24h) — without this,
        # one test's rendered page (with or without the widget) is served
        # verbatim to the next.
        cache.clear()

    def test_widget_mounts_with_character_context(self):
        char = self.alpha['characters']['Alice']
        resp = self.client.get(
            f'/explore/alpha-show/characters/{char.fabula_uuid}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('fabula-chat-context', body)
        self.assertIn('"page_type": "character"', body)
        self.assertIn('chat-widget.js', body)

    @override_settings(CHAT_ENABLED=False)
    def test_widget_absent_when_disabled(self):
        cache.clear()
        char = self.alpha['characters']['Alice']
        resp = self.client.get(
            f'/explore/alpha-show/characters/{char.fabula_uuid}/')
        self.assertNotIn('fabula-chat-context', resp.content.decode())
