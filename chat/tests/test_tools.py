from chat.registry import execute_tool

from .base import NarrativeGraphTestCase


class ResolveEntityTests(NarrativeGraphTestCase):
    def test_finds_character_by_partial_name(self):
        result = execute_tool('resolve_entity',
                              {'series': 'alpha-show', 'query': 'Alice'})
        names = [m['name'] for m in result['matches']]
        self.assertIn('Alice Alpha', names)
        self.assertNotIn('Alice Beta', names)  # series isolation

    def test_unknown_series_lists_available(self):
        result = execute_tool('resolve_entity',
                              {'series': 'nope', 'query': 'Alice'})
        self.assertIn('alpha-show', result['error'])

    def test_no_match_returns_empty_with_note(self):
        result = execute_tool('resolve_entity',
                              {'series': 'alpha-show', 'query': 'Zorblax'})
        self.assertEqual(result['matches'], [])
        self.assertIn('note', result)


class CharacterToolTests(NarrativeGraphTestCase):
    def test_profile_shape(self):
        result = execute_tool('get_character', {
            'series': 'alpha-show', 'character': 'Alice Alpha'})
        self.assertEqual(result['name'], 'Alice Alpha')
        self.assertTrue(result['url'].startswith('/characters/'))
        co = result['most_frequent_co_participants']
        self.assertEqual(co[0]['name'], 'Bob Alpha')
        self.assertEqual(co[0]['shared_events'], 3)
        self.assertEqual(result['arcs'][0]['title'], 'The Alpha Feud')

    def test_resolves_by_uuid(self):
        result = execute_tool('get_character', {
            'series': 'alpha-show', 'character': 'agent_Alpha_alice'})
        self.assertEqual(result['name'], 'Alice Alpha')

    def test_cross_series_character_not_found(self):
        result = execute_tool('get_character', {
            'series': 'alpha-show', 'character': 'Alice Beta'})
        self.assertIn('error', result)

    def test_timeline_in_story_order(self):
        result = execute_tool('character_timeline', {
            'series': 'alpha-show', 'character': 'Alice Alpha'})
        titles = [i['event']['title'] for i in result['timeline']]
        self.assertEqual(titles, ['Alpha Event 1', 'Alpha Event 2',
                                  'Alpha Event 3'])
        self.assertEqual(result['total_participations'], 3)
        first = result['timeline'][0]
        self.assertEqual(first['event']['episode'], 'S1E1')
        self.assertIn('acted in', first['what_happened'])

    def test_relationship_history(self):
        result = execute_tool('relationship_history', {
            'series': 'alpha-show', 'character_a': 'Alice Alpha',
            'character_b': 'Bob Alpha'})
        self.assertEqual(result['total_shared_events'], 3)
        event = result['shared_events'][0]
        self.assertIn('Alice Alpha', event)
        self.assertIn('Bob Alpha', event)


class EpisodeAndStorylineTests(NarrativeGraphTestCase):
    def test_get_episode(self):
        result = execute_tool('get_episode', {
            'series': 'alpha-show', 'season': 1, 'episode': 1})
        self.assertEqual(result['episode'], 'S1E1')
        self.assertEqual(result['event_count'], 2)

    def test_missing_episode_lists_available(self):
        result = execute_tool('get_episode', {
            'series': 'alpha-show', 'season': 9, 'episode': 9})
        self.assertIn('error', result)
        self.assertEqual(result['available_episodes'], ['S1E1', 'S1E2'])

    def test_list_storylines(self):
        result = execute_tool('list_storylines', {'series': 'alpha-show'})
        arcs = result['conflict_arcs']
        self.assertEqual(len(arcs), 1)
        self.assertEqual(arcs[0]['title'], 'The Alpha Feud')
        self.assertEqual(arcs[0]['event_count'], 2)

    def test_get_arc_with_roles(self):
        result = execute_tool('get_arc', {
            'series': 'alpha-show', 'arc': 'Alpha Feud'})
        roles = [(e['title'], e['arc_role']) for e in result['events']]
        self.assertEqual(roles, [('Alpha Event 1', 'START'),
                                 ('Alpha Event 3', 'CLIMAX')])


class ConnectionToolTests(NarrativeGraphTestCase):
    def test_connections_for_event(self):
        result = execute_tool('connections_for_event', {
            'series': 'alpha-show', 'event': 'Alpha Event 2'})
        self.assertEqual(result['incoming_total'], 1)
        self.assertEqual(result['outgoing_total'], 1)
        self.assertEqual(result['outgoing'][0]['type'], 'FORESHADOWING')
        self.assertEqual(result['outgoing'][0]['other_event']['title'],
                         'Alpha Event 3')

    def test_connection_path_multi_hop(self):
        result = execute_tool('connection_path', {
            'series': 'alpha-show', 'from_event': 'event_Alpha1',
            'to_event': 'event_Alpha3'})
        self.assertTrue(result['path_found'])
        self.assertEqual(result['hop_count'], 2)
        self.assertEqual([h['type'] for h in result['path']],
                         ['CAUSAL', 'FORESHADOWING'])
        self.assertFalse(result['path'][0]['walked_against_direction'])

    def test_connection_path_respects_series_boundary(self):
        result = execute_tool('connection_path', {
            'series': 'alpha-show', 'from_event': 'event_Alpha1',
            'to_event': 'event_Beta3'})
        self.assertIn('error', result)  # target unresolvable in alpha

    def test_search_events_matches_dialogue(self):
        result = execute_tool('search_events', {
            'series': 'alpha-show', 'query': 'Line 2 of Alpha'})
        self.assertEqual(result['total_matches'], 1)
        self.assertEqual(result['results'][0]['title'], 'Alpha Event 2')

    def test_graph_stats_scoped(self):
        result = execute_tool('graph_stats', {'series': 'alpha-show'})
        self.assertEqual(result['events'], 3)
        self.assertEqual(result['characters'], 2)
        self.assertEqual(result['connections_total'], 2)
        self.assertEqual(result['cross_episode_connections'], 1)
        self.assertEqual(result['connections_by_type'],
                         {'CAUSAL': 1, 'FORESHADOWING': 1})


class ExecutorTests(NarrativeGraphTestCase):
    def test_unknown_tool(self):
        self.assertIn('error', execute_tool('drop_tables', {}))

    def test_bad_arguments_reflected(self):
        result = execute_tool('get_character', {'series': 'alpha-show',
                                                'bogus': 'x'})
        self.assertIn('error', result)
