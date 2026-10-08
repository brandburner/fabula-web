"""Rich links, chips, and sanitization — all deterministic, all pure."""

from django.test import SimpleTestCase

from chat.chips import followup_chips, welcome_chips
from chat.rich_links import extract_rich_links
from chat.sanitize import build_tool_context, sanitize_tool_context


class RichLinkTests(SimpleTestCase):
    def test_walks_nested_results_dedupes_and_caps(self):
        collected = [{
            'tool': 'character_timeline',
            'args': {},
            'result': {
                'character': {'name': 'Alice', 'url': '/characters/a1/'},
                'timeline': [
                    {'event': {'title': f'E{i}', 'url': f'/events/e{i}/',
                               'episode': 'S1E1'}}
                    for i in range(10)
                ] + [
                    # duplicate URL must not double-count
                    {'event': {'title': 'E0', 'url': '/events/e0/'}},
                ],
            },
        }]
        cards = extract_rich_links(collected)
        self.assertEqual(len(cards), 6)  # capped
        self.assertEqual(cards[0]['kind'], 'character')
        self.assertEqual(cards[0]['title'], 'Alice')
        self.assertEqual(cards[1]['subtitle'], 'S1E1')
        urls = [c['url'] for c in cards]
        self.assertEqual(len(urls), len(set(urls)))

    def test_ignores_external_and_unlabeled(self):
        collected = [{'tool': 't', 'args': {}, 'result': {
            'url': 'https://evil.example/x', 'name': 'Evil',
            'inner': {'url': '/no-label/'},
        }}]
        self.assertEqual(extract_rich_links(collected), [])


class ChipTests(SimpleTestCase):
    def test_welcome_chips_per_page_type(self):
        chips = welcome_chips('character', entity_name='Alice')
        self.assertTrue(all('Alice' in c['label'] or 'Alice' in c['send']
                            for c in chips))
        self.assertTrue(welcome_chips('unknown-page-type'))

    def test_followups_seeded_from_results(self):
        collected = [{
            'tool': 'get_character', 'args': {},
            'result': {
                'name': 'Alice', 'url': '/characters/a1/',
                'most_frequent_co_participants': [
                    {'name': 'Bob', 'shared_events': 3}],
            },
        }]
        chips = followup_chips(collected)
        labels = ' '.join(c['label'] for c in chips)
        self.assertIn("Alice's timeline", labels)
        self.assertIn('Bob', labels)
        outward = [c for c in chips if c.get('url')]
        self.assertTrue(all(c['url'].startswith('/') for c in outward))

    def test_error_results_produce_no_entity_chips(self):
        collected = [{'tool': 'get_character', 'args': {},
                      'result': {'error': 'nope'}}]
        chips = followup_chips(collected)
        self.assertTrue(all('storylines' in c['label'].lower()
                            for c in chips))


class ToolContextTests(SimpleTestCase):
    def test_round_trip_survives_sanitization(self):
        collected = [{
            'tool': 'get_character', 'args': {},
            'result': {'name': 'Alice', 'uuid': 'agent_a1',
                       'url': '/characters/a1/'},
        }]
        echo = sanitize_tool_context(build_tool_context(collected))
        self.assertEqual(len(echo), 1)
        self.assertEqual(echo[0]['digest']['name'], 'Alice')
        self.assertEqual(echo[0]['digest']['uuid'], 'agent_a1')

    def test_hostile_input_stripped(self):
        hostile = [
            {'tool': 'not_a_tool', 'digest': {'name': 'x'}},
            {'tool': 'graph_stats', 'digest': {'__proto__': 'x'}},
            {'tool': 'graph_stats', 'digest': {'name': 'A' * 10000}},
            {'tool': 'graph_stats', 'digest': 'not-a-dict'},
            42,
        ]
        cleaned = sanitize_tool_context(hostile)
        self.assertEqual(len(cleaned), 1)  # only the oversized-name one...
        self.assertEqual(len(cleaned[0]['digest']['name']), 200)  # ...capped
