import copy
import io
import json
import uuid

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from adventure import explore, narrator, projection
from adventure.models import Playthrough
from adventure.tests import world_fixture


class ProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = world_fixture.build()
        projection.cached_world.cache_clear()

    def setUp(self):
        self.world = projection.build_world(self.fx['episode'], 'test-show-e1')
        explore.ensure_index(self.world)

    # ---------------------------------------------------------- projection
    def test_world_reads_only_live_pages_in_presentation_order(self):
        self.assertEqual([e['uuid'] for e in self.world['events']], ['evt_1', 'evt_2', 'evt_3', 'evt_4', 'evt_5'])
        self.assertEqual(self.world['episode']['title'], 'The Ledger')
        self.assertEqual(self.world['events'][0]['title'], 'Arrival at the Hall')
        self.assertNotIn('<', self.world['events'][0]['description'])

    def test_rooms_features_ancestors_and_mentions(self):
        locs = self.world['locations']
        self.assertTrue(locs['loc_hall']['room'] and locs['loc_study']['room'] and locs['loc_inn']['room'])
        self.assertFalse(locs['loc_yard']['room'])                 # involvement only
        self.assertTrue(locs['loc_yard']['in_episode'])
        self.assertFalse(locs['loc_manor']['in_episode'])          # ancestor pulled in for containment
        self.assertEqual(locs['loc_manor']['children'], ['loc_hall'])
        self.assertEqual(locs['loc_study']['mentions'], [0])        # mentioned at evt_1, primary at evt_2
        self.assertEqual(locs['loc_study']['moments'], [1])

    def test_report_counts_coverage_and_placeholders(self):
        rep = self.world['report']
        self.assertEqual(rep['events'], 5)
        self.assertEqual(rep['rooms'], 3)
        self.assertEqual(rep['feature_locations'], 1)
        self.assertEqual(rep['events_without_location_involvement'], 1)
        self.assertEqual(rep['events_without_objects'], 2)
        self.assertEqual(rep['flashbacks'], 1)
        self.assertEqual(rep['rooms_with_parent'], 2)
        self.assertEqual(rep['ancestors_outside_episode'], 1)
        self.assertEqual(self.world['events'][2]['dialogue'], [])   # "(No direct dialogue occurs.)" dropped
        self.assertEqual(self.world['events'][0]['dialogue'], ['Alice: Where is it?'])

    def test_report_command(self):
        out = io.StringIO()
        call_command('world_report', '--series', 'test-show', '--episode', '1', stdout=out)
        self.assertIn('events: 5', out.getvalue())

    # ------------------------------------------------------------- engine
    def play(self, state, command, backend='local'):
        status, payload = explore.parse(self.world, state, command)
        self.assertEqual(status, 'action', (command, status, payload))
        key = explore.gap(self.world, state, payload)
        written = narrator.write(self.world, state, key, backend) if key else None
        return explore.transition(self.world, state, payload, written)

    def test_look_is_written_from_the_record_once_then_replayed(self):
        state = explore.new_state(self.world)
        state, out = self.play(state, 'look')
        text = out[1]['text']
        self.assertEqual(out[0]['kind'], 'written')
        self.assertIn('GREAT HALL', text)
        self.assertIn('Quiet in Great Hall', text)
        self.assertIn("Ward's Study", text)                        # feature place at this moment
        self.assertIn('Present: Alice Ward, Bob Ward.', text)
        self.assertNotIn('foreshadowing', text)                     # retrospective analysis kept out
        self.assertEqual(state['passages']['look:evt_1']['sources'][0]['model'], 'LocationInvolvement')
        self.assertNotIn('The long hall of the manor', text)      # Location.description is evidence, not narration
        state, again = self.play(state, 'look around')
        self.assertEqual(again[0]['text'], text)
        self.assertEqual((state['authored'], state['replays']), (1, 1))

    def test_navigation_prefers_a_places_own_moments(self):
        state = explore.new_state(self.world)
        state, out = self.play(state, 'go to the study')          # mentioned at evt_1, primary at evt_2
        self.assertEqual(state['event'], 'evt_2')
        self.assertIn('a recollection', out[-1]['text'])
        state, _ = self.play(state, 'leave')                        # study -> hall's next moment
        self.assertEqual(state['event'], 'evt_4')
        state, out = self.play(state, 'go to stable yard')          # feature only: falls back to its mention
        self.assertEqual(state['event'], 'evt_3')
        self.assertIn('part of this moment', out[1]['text'])
        state, _ = self.play(state, 'next')
        self.assertEqual(state['event'], 'evt_4')
        state, _ = self.play(state, 'back')
        self.assertEqual(state['event'], 'evt_3')
        self.assertEqual(explore.parse(self.world, state, 'crown inn'), ('action', 'where'))   # already here
        state, _ = self.play(state, 'next')
        state, out = self.play(state, 'the study')                  # bare place name, no later moment -> wraps
        self.assertEqual(state['event'], 'evt_2')
        self.assertIn('no later moment', out[0]['text'])

    def test_examine_never_substitutes_a_target(self):
        state = explore.new_state(self.world)
        self.assertEqual(explore.parse(self.world, state, 'examine ward'), ('ambiguous', ['Alice Ward', 'Bob Ward']))
        self.assertEqual(explore.parse(self.world, state, 'examine alice'), ('action', 'char:agent_alice'))
        self.assertEqual(explore.parse(self.world, state, 'x the ledger'), ('action', 'obj:object_ledger'))
        self.assertEqual(explore.parse(self.world, state, 'examine innkeeper'), ('absent', 'innkeeper'))
        self.assertEqual(explore.parse(self.world, state, 'examine dragon'), ('unknown', None))
        self.assertEqual(explore.parse(self.world, state, 'examine the hall'), ('action', 'look'))
        self.assertEqual(explore.parse(self.world, state, 'what does alice want'), ('action', 'mind:agent_alice'))
        state['event'] = 'evt_4'
        self.assertEqual(explore.parse(self.world, state, 'examine cloak')[0], 'ambiguous')
        self.assertEqual(explore.parse(self.world, state, 'examine the dark cloak'), ('action', 'obj:object_cloak'))

    def test_mind_is_labelled_interpretation_and_needs_no_passage(self):
        state = explore.new_state(self.world)
        self.assertIsNone(explore.gap(self.world, state, 'mind:agent_alice'))
        state, out = self.play(state, 'what does alice want')
        self.assertIn('interpretation', out[0]['text'])
        self.assertIn('find the ledger', out[0]['text'])
        self.assertEqual(state['passages'], {})

    def test_frozen_world_refuses_unwritten_passages_only(self):
        state = explore.new_state(self.world)
        state, _ = self.play(state, 'watch')
        state['frozen'] = True
        self.assertIsNone(explore.gap(self.world, state, 'look'))
        state, out = self.play(state, 'look')
        self.assertEqual(out[0]['kind'], 'system')
        self.assertNotIn('look:evt_1', state['passages'])
        state, out = self.play(state, 'watch')
        self.assertIn('Alice Ward does something', out[0]['text'])

    def test_learned_alias_is_world_scoped_and_validated(self):
        state = explore.new_state(self.world)
        state['parser_aliases'] = {'peer at alice': 'char:agent_alice', 'peer at keeper': 'char:agent_keeper'}
        self.assertEqual(explore.parse(self.world, state, 'peer at alice'), ('action', 'char:agent_alice'))
        self.assertEqual(explore.parse(self.world, state, 'peer at keeper'), ('unknown', None))  # not present here
        self.assertEqual([c['action'] for c in explore.candidates(self.world, state, 'peer at alice')], ['char:agent_alice', 'mind:agent_alice'])
        self.assertEqual(explore.candidates(self.world, state, 'peer at alice and bob'), [])

    def test_compile_matches_every_live_transition(self):
        state = explore.new_state(self.world)
        for command in ('look', 'watch', 'examine alice', 'next', 'look'):
            state, _ = self.play(state, command)
        compiled = explore.compile_world(self.world, state)
        self.assertEqual(set(compiled['states']), {e['uuid'] for e in self.world['events']})
        for key, entry in compiled['states'].items():
            sample = copy.deepcopy(state)
            sample.update(event=key, visited=[key], frozen=True, moves=0, replays=0)
            self.assertEqual(set(entry['actions']), set(explore.available(self.world, sample)))
            for action, result in entry['actions'].items():
                after, blocks = explore.transition(self.world, sample, action)
                self.assertEqual((result['next'], result['blocks']), (explore.state_key(after), blocks), action)
            self.assertEqual(entry['aliases'].get('examine alice'), 'char:agent_alice' if 'char:agent_alice' in entry['actions'] else None)
        self.assertEqual(compiled['states']['evt_1']['actions']['look']['blocks'][0]['text'], state['passages']['look:evt_1']['text'])
        self.assertEqual(compiled['aliases']['go to crown inn'], 'go:loc_inn')

    def test_narrator_rejects_invalid_model_output(self):
        from unittest.mock import patch
        from chat.llm import LLMError
        state = explore.new_state(self.world)
        with patch('adventure.narrator.OpenRouterClient') as client:
            client.return_value.stream_completion.return_value = iter([{'kind': 'final', 'content': '{"text": "short"}'}])
            with self.assertRaises(LLMError):
                narrator.write(self.world, state, 'look:evt_1', 'openrouter')
            client.return_value.stream_completion.return_value = iter([{'kind': 'final', 'content': json.dumps({'text': 'You stand in the long hall. ' * 4})}])
            passage = narrator.write(self.world, state, 'look:evt_1', 'openrouter')
        self.assertEqual(passage['backend'], 'openrouter')
        self.assertTrue(passage['sources'])


@override_settings(ADVENTURE_ENABLED=True, ADVENTURE_AUTHOR_BACKEND='local', ADVENTURE_WORLDS=[world_fixture.WORLD],
                   CHAT_RATE_LIMIT_PER_MINUTE=1000, CHAT_RATE_LIMIT_PER_HOUR=1000)
class ProjectionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = world_fixture.build()
        projection.cached_world.cache_clear()

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.base = '/play/test-show-e1/'
        self.state = self.client.get(self.base + 'api/state/').json()

    def command(self, command, client=None):
        client = client or self.client
        response = client.post(self.base + 'api/turn/', data=json.dumps({
            'command': command, 'version': self.state['version'], 'request_id': str(uuid.uuid4())}),
            content_type='application/json')
        if response.status_code == 200:
            self.state = response.json()
        return response

    def test_world_pages_and_state(self):
        self.assertEqual(self.state['scene']['name'], 'Great Hall (Ashby Manor)')
        self.assertEqual(self.state['viewpoint'], 'Unseen witness')
        self.assertEqual(self.state['revision'], 'projection-v1')
        for url in (self.base, self.base + 'embed/'):
            response = self.client.get(url)
            self.assertContains(response, 'data-api="/play/test-show-e1/api/"')
            self.assertContains(response, 'Test Show S01E01')
        self.assertEqual(self.client.get('/play/no-such-world/').status_code, 404)

    def test_turns_persist_passages_and_position(self):
        self.command('look')
        self.command('go to the crown inn')
        self.assertEqual(self.state['scene']['name'], 'The Crown Inn')
        self.assertEqual(self.state['authored'], 1)
        self.assertEqual([o['name'] for o in self.state['objects']], ['the view · Arrival at the Hall'])
        self.assertEqual(self.client.get(self.base + 'api/state/').json(), self.state)
        self.assertTrue(self.command('examine ward').json()['transcript'][-1]['text'].startswith('BOB WARD'))  # only Bob is here
        self.assertEqual(self.command('examine innkeeper').json()['transcript'][-1]['kind'], 'narration')
        self.assertEqual(self.command('examine alice').json()['transcript'][-1]['kind'], 'system')          # absent

    def test_worlds_have_separate_saves_from_dracula(self):
        dracula = self.client.get('/play/api/state/').json()
        self.command('next')
        self.assertEqual(self.client.get('/play/api/state/').json(), dracula)
        self.assertEqual(Playthrough.objects.count(), 2)
        self.assertEqual(set(Playthrough.objects.values_list('scenario_revision', flat=True)),
                         {'dracula-interview-v1', 'test-show-e1:projection-v1'})

    def test_restart_keeps_passages(self):
        self.command('look')
        self.command('next')
        self.command('restart story')
        self.assertEqual(self.state['scene']['time'], 'Moment 1 of 5 · Scene 1')
        self.assertEqual(self.state['authored'], 1)

    def test_download_is_standalone(self):
        self.command('look')
        response = self.client.get(self.base + 'download/')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="fabula-test-show-e1-written-world.html"')
        body = response.content.decode()
        self.assertIn('compiled-world', body)
        self.assertIn('Quiet in Great Hall', body)
        self.assertNotIn('/static/', body)

    def test_unpublished_episode_is_not_a_world(self):
        with override_settings(ADVENTURE_WORLDS=[{'slug': 'hidden', 'series': 'test-show', 'season': 1, 'episode': 2}]):
            self.assertEqual(self.client.get('/play/hidden/api/state/').status_code, 404)
