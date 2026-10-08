import copy
import io
import json
import uuid

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from django.core.management import CommandError

from adventure import explore, narrator, projection, store
from adventure.models import Playthrough, WorldPassage
from narrative.models import LocationInvolvement
from adventure.tests import world_fixture


class GroundingTests(TestCase):
    DATA = {'kind': 'look', 'room': 'Great Hall', 'present': ['Alice Ward'], 'objects': ['Patch'],
            'places': [{'name': 'Great Hall', 'primary': True, 'atmosphere': 'Quiet and cold.', 'access': '',
                        'details': ['a cold hearth', 'rain on the glass']}]}

    def problems(self, text, data=None):
        return narrator.grounding_problems(text, data or self.DATA)

    def test_a_faithful_paraphrase_passes(self):
        self.assertEqual(self.problems('You are in the Great Hall. It is quiet and cold; rain runs down the glass '
                                       'beside a cold hearth. Alice Ward is here, and Patch.'), [])

    def test_additions_are_named(self):
        self.assertIn('names what the record does not: Henry', self.problems('Alice Ward waits for Henry in the hall.')[0])
        self.assertIn('interprets: symbol', self.problems('The cold hearth is a symbol of her loss.'))
        self.assertIn('numbers not in the record: 3', self.problems('Rain on the glass at 3 in the hall.'))
        self.assertIn('treats the name Patch as a common noun', self.problems('Alice Ward is here. There is also a patch.'))
        self.assertTrue(self.problems('Velvet tapestries, gilded mirrors and a roaring banquet fill the chamber.')[-1]
                        .startswith('drifts from the record'))

    def test_wording_the_record_already_uses_is_not_an_addition(self):
        data = {**self.DATA, 'places': [{**self.DATA['places'][0], 'atmosphere': 'A symbol of decay; the patch of damp spreads.'}]}
        self.assertEqual(self.problems('The Great Hall is a symbol of decay. The patch of damp spreads.', data), [])


class ProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = world_fixture.build()
        projection.cached_world.cache_clear()

    def setUp(self):
        self.world = projection.build_world(self.fx['episode'], 'test-show-e1')
        explore.ensure_index(self.world)
        self.written = {}                                           # stands in for the shared store

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
        self.assertEqual(rep['events_without_objects'], 1)
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
        key = explore.needs_passage(self.world, state, payload)
        passage, fresh = (self.written.get(key), False) if key else (None, False)
        if key and passage is None and not state['frozen']:
            passage = self.written[key] = narrator.write(self.world, key, backend)
            fresh = True
        return explore.transition(self.world, state, payload, passage, fresh)

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
        self.assertEqual(self.written['look:evt_1']['sources'][0]['model'], 'LocationInvolvement')
        self.assertEqual(state['seen'], ['look:evt_1'])
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

    def test_an_owner_name_never_identifies_the_thing(self):
        state = explore.new_state(self.world)
        state['event'] = 'evt_3'                                    # Bob has Alice's Ledger at the inn; Alice is absent
        self.assertEqual(explore.parse(self.world, state, 'examine alice'), ('absent', 'alice'))
        self.assertEqual(explore.parse(self.world, state, 'examine ledger'), ('action', 'obj:object_ledger'))
        self.assertEqual(explore.parse(self.world, state, "examine alice's ledger"), ('action', 'obj:object_ledger'))
        state['event'] = 'evt_1'
        self.assertEqual(explore.parse(self.world, state, 'go to ward'), ('action', 'go:loc_study'))   # places accept owners

    def test_dash_prefix_names_the_container_not_the_thing(self):
        vs = explore.variants('York Place - Upper Chamber (Stormy Night)')
        self.assertIn('upper chamber', vs)
        self.assertNotIn('york place', vs)

    def test_containment_breaks_ties_between_places(self):
        found = [('go:loc_yard', 'Stable Yard (The Crown Inn)'), ('go:loc_inn', 'The Crown Inn')]
        self.assertEqual(explore.container_of(self.world, found), [('go:loc_inn', 'The Crown Inn')])
        unrelated = [('go:loc_yard', 'Stable Yard (The Crown Inn)'), ('go:loc_study', "Ward's Study (Ashby Manor)")]
        self.assertEqual(explore.container_of(self.world, unrelated), unrelated)

    def test_mind_is_labelled_interpretation_and_needs_no_passage(self):
        state = explore.new_state(self.world)
        self.assertIsNone(explore.needs_passage(self.world, state, 'mind:agent_alice'))
        state, out = self.play(state, 'what does alice want')
        self.assertIn('interpretation', out[0]['text'])
        self.assertIn('find the ledger', out[0]['text'])
        self.assertEqual((self.written, state['seen']), ({}, []))

    def test_frozen_world_refuses_unwritten_passages_only(self):
        state = explore.new_state(self.world)
        state, _ = self.play(state, 'watch')
        state['frozen'] = True
        state, out = self.play(state, 'look')
        self.assertEqual(out[0]['kind'], 'system')
        self.assertNotIn('look:evt_1', self.written)
        self.assertNotIn('look:evt_1', state['seen'])
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
        compiled = explore.compile_world(self.world, state, self.written)
        self.assertEqual(set(compiled['states']), {e['uuid'] for e in self.world['events']})
        for key, entry in compiled['states'].items():
            sample = copy.deepcopy(state)
            sample.update(event=key, visited=[key], frozen=True, moves=0, replays=0)
            self.assertEqual(set(entry['actions']), set(explore.available(self.world, sample)))
            for action, result in entry['actions'].items():
                after, blocks = explore.transition(self.world, sample, action,
                                                   self.written.get(explore.passage_key(sample, action) or ''))
                self.assertEqual((result['next'], result['blocks']), (explore.state_key(after), blocks), action)
            self.assertEqual(entry['aliases'].get('examine alice'), 'char:agent_alice' if 'char:agent_alice' in entry['actions'] else None)
        self.assertEqual(compiled['states']['evt_1']['actions']['look']['blocks'][0]['text'], self.written['look:evt_1']['text'])
        self.assertEqual(compiled['states']['evt_3']['actions']['look']['blocks'][0]['kind'], 'system')   # unwritten
        self.assertEqual(compiled['aliases']['go to crown inn'], 'go:loc_inn')

    def test_narrator_rejects_invalid_model_output(self):
        from unittest.mock import patch
        from chat.llm import LLMError
        state = explore.new_state(self.world)
        with patch('adventure.narrator.OpenRouterClient') as client:
            client.return_value.stream_completion.return_value = iter([{'kind': 'final', 'content': '{"text": "short"}'}])
            with self.assertRaises(LLMError):
                narrator.write(self.world, 'look:evt_1', 'openrouter')
            client.return_value.stream_completion.return_value = iter([{'kind': 'final', 'content': json.dumps({'text': 'You stand in the long hall. ' * 4})}])
            passage = narrator.write(self.world, 'look:evt_1', 'openrouter')
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
        projection.cached_world.cache_clear()                       # a test may edit the record; rollback doesn't reach the cache
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

    # ------------------------------------------------- shared world passages
    def test_a_passage_written_by_one_visitor_serves_the_next(self):
        self.command('look')
        first = self.state['transcript'][-2]['text']
        other = Client()
        self.state = other.get(self.base + 'api/state/').json()
        self.assertEqual(self.state['authored'], 1)                 # the world already holds it
        self.command('look', client=other)
        self.assertEqual(self.state['transcript'][-2]['text'], first)
        self.assertNotEqual(self.state['transcript'][-3]['kind'], 'written')   # replayed, not rewritten
        self.assertEqual(WorldPassage.objects.count(), 1)
        self.assertEqual(WorldPassage.objects.get().written_by, Playthrough.objects.order_by('created_at').first())

    def test_frozen_visitor_reads_the_world_but_writes_nothing(self):
        other = Client()
        self.command('look')
        self.state = other.get(self.base + 'api/state/').json()
        self.command('freeze world', client=other)
        self.command('look', client=other)
        self.assertIn('Quiet in Great Hall', self.state['transcript'][-2]['text'])
        self.command('watch', client=other)
        self.assertEqual(self.state['transcript'][-1]['kind'], 'system')
        self.assertEqual(WorldPassage.objects.count(), 1)

    def test_a_changed_record_retires_its_passage(self):
        self.command('look')
        LocationInvolvement.objects.filter(event__fabula_uuid='evt_1', location__fabula_uuid='loc_hall').update(
            observed_atmosphere='Loud in the Great Hall.')
        projection.cached_world.cache_clear()
        self.state = self.client.get(self.base + 'api/state/').json()
        self.assertEqual(self.state['authored'], 0)                 # old passage no longer matches the record
        self.command('look')
        self.assertIn('Loud in the Great Hall', self.state['transcript'][-2]['text'])
        self.assertEqual(WorldPassage.objects.count(), 2)            # the old one is kept as history

    def test_each_backend_is_written_once_for_the_world(self):
        from unittest.mock import patch
        self.command('look')
        with override_settings(CHAT_OPENROUTER_API_KEY='test-key'), \
                patch('adventure.narrator.render_openrouter', return_value='You stand in the long hall, rain on the glass.') as llm:
            self.command('use live author')
            self.command('look')
            self.assertIn('You stand in the long hall', self.state['transcript'][-2]['text'])
            self.command('look')
            self.assertEqual(llm.call_count, 1)
            self.assertEqual(self.state['model_calls'], 1)
            with override_settings(ADVENTURE_WORLD_LLM_BUDGET=1):
                response = self.command('watch')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(set(WorldPassage.objects.values_list('backend', flat=True)), {'local', 'openrouter'})

    def test_download_contains_passages_other_visitors_wrote(self):
        self.command('look')
        body = Client().get(self.base + 'download/').content.decode()
        self.assertIn('Quiet in Great Hall', body)

    # ------------------------------------------- grounding check and retiring
    def test_a_refused_llm_passage_falls_back_to_the_record_and_attempts_are_capped(self):
        from unittest.mock import patch
        bad = 'You are in the Great Hall. Henry the Eighth waits beside a velvet throne under gilded banners.'
        with override_settings(CHAT_OPENROUTER_API_KEY='test-key'), \
                patch('adventure.narrator.render_openrouter', return_value=bad) as llm:
            visitors = [self.client, Client(), Client()]
            for n, visitor in enumerate(visitors):
                self.state = visitor.get(self.base + 'api/state/').json()
                self.command('use live author', client=visitor)
                self.command('look', client=visitor)
                text = '\n'.join(b['text'] for b in self.state['transcript'][-4:])
                self.assertIn('Quiet in Great Hall', text)              # the record itself
                self.assertNotIn('Henry', text)
                if n < 2:
                    self.assertIn('added to the record', text)
            self.assertEqual(llm.call_count, 2)                          # third visitor: attempts exhausted
        refused = WorldPassage.objects.filter(backend='openrouter')
        self.assertEqual(refused.count(), 2)
        self.assertTrue(all(r.retired_at and r.retired_reason.startswith('grounding: names') for r in refused))
        self.assertEqual(WorldPassage.objects.filter(backend='local', retired_at__isnull=True).count(), 1)

    def test_retire_command_dry_run_apply_and_rewrite(self):
        import io
        from django.core.management import call_command
        self.command('look')
        key = 'look:evt_1'
        out = io.StringIO()
        call_command('retire_passage', 'test-show-e1', key, stdout=out, skip_checks=False)   # the real CLI path
        self.assertIn('Dry run', out.getvalue())
        self.assertEqual(WorldPassage.objects.filter(retired_at__isnull=True).count(), 1)
        call_command('retire_passage', 'test-show-e1', key, '--reason', 'test', '--apply', stdout=out)
        self.assertEqual(WorldPassage.objects.get().retired_reason, 'test')
        self.command('look')                                             # rewritten on next request
        self.assertEqual(self.state['transcript'][-3]['kind'], 'written')
        self.assertEqual((WorldPassage.objects.count(), WorldPassage.objects.filter(retired_at__isnull=True).count()), (2, 1))
        listing = io.StringIO()
        call_command('retire_passage', 'test-show-e1', '--list', '--retired', stdout=listing)
        self.assertIn('retired · test', listing.getvalue())

    def test_retire_command_check_sweeps_ungrounded_llm_passages(self):
        import io
        from django.core.management import call_command
        world = projection.load_world(world_fixture.WORLD)
        explore.ensure_index(world)
        store.save('test-show-e1', world, 'look:evt_1', {'text': 'You see King Henry at a velvet throne.', 'backend': 'openrouter',
                                                         'kind': 'look', 'sources': []})
        store.save('test-show-e1', world, 'watch:evt_1', {'text': 'Alice Ward does something in the hall.', 'backend': 'openrouter',
                                                          'kind': 'watch', 'sources': []})
        out = io.StringIO()
        call_command('retire_passage', 'test-show-e1', '--check', stdout=out)
        self.assertIn('1 of 2 live LLM passage(s) fail', out.getvalue())
        call_command('retire_passage', 'test-show-e1', '--check', '--apply', stdout=out)
        self.assertEqual(list(store.live('test-show-e1').values_list('key', flat=True)), ['watch:evt_1'])
        with self.assertRaises(CommandError):
            call_command('retire_passage', 'dracula', '--list', stdout=io.StringIO())

    # ------------------------------------------- carry-forward and the budget window
    GROUNDED = 'You are in the Great Hall. It is quiet; rain is on the glass beside a cold hearth.'

    def llm_passage(self, text=None):
        world = projection.load_world(world_fixture.WORLD)
        explore.ensure_index(world)
        return store.save('test-show-e1', world, 'look:evt_1', {'text': text or self.GROUNDED, 'backend': 'openrouter',
                                                                'kind': 'look', 'sources': []})

    def change_record(self, **fields):
        LocationInvolvement.objects.filter(event__fabula_uuid='evt_1').update(**fields)
        projection.cached_world.cache_clear()

    def test_a_passage_that_still_fits_a_changed_record_is_carried_forward_free(self):
        from unittest.mock import patch
        original = self.llm_passage()
        self.change_record(observed_atmosphere='Quiet and still in the hall.')
        with override_settings(CHAT_OPENROUTER_API_KEY='test-key'), \
                patch('adventure.narrator.render_openrouter') as llm:
            self.command('use live author')
            self.command('look')
            self.assertEqual(llm.call_count, 0)
        self.assertEqual(self.state['transcript'][-2]['text'], self.GROUNDED)
        carried = WorldPassage.objects.get(carried_from__isnull=False)
        self.assertEqual(carried.carried_from_id, original['id'])
        self.assertNotEqual(carried.packet_hash, WorldPassage.objects.get(pk=original['id']).packet_hash)
        self.assertEqual(store.llm_spent('test-show-e1'), 1)            # the carry cost nothing

    def test_a_passage_that_no_longer_fits_is_retired_and_rewritten(self):
        from unittest.mock import patch
        original = self.llm_passage()
        self.change_record(observed_atmosphere='Loud with music.', key_environmental_details=['a roaring fire', 'dancers'])
        with override_settings(CHAT_OPENROUTER_API_KEY='test-key'), \
                patch('adventure.narrator.render_openrouter', return_value='You are in the Great Hall. It is loud with music; dancers turn by a roaring fire.') as llm:
            self.command('use live author')
            self.command('look')
            self.assertEqual(llm.call_count, 1)
        self.assertIn('dancers', self.state['transcript'][-2]['text'])
        self.assertTrue(WorldPassage.objects.get(pk=original['id']).retired_reason.startswith('stale: no longer grounded'))

    def test_the_budget_is_a_rolling_window(self):
        from datetime import timedelta
        from django.utils import timezone
        self.llm_passage()
        with override_settings(ADVENTURE_WORLD_LLM_BUDGET=1, ADVENTURE_WORLD_LLM_WINDOW_DAYS=30):
            self.assertFalse(store.llm_budget_left('test-show-e1'))
            WorldPassage.objects.update(created_at=timezone.now() - timedelta(days=31))
            self.assertTrue(store.llm_budget_left('test-show-e1'))

    def test_carry_forward_sweep(self):
        import io
        from django.core.management import call_command
        self.llm_passage()
        self.change_record(observed_atmosphere='Quiet and still in the hall.')
        out = io.StringIO()
        call_command('retire_passage', 'test-show-e1', '--carry-forward', stdout=out)
        self.assertIn('1 would carry forward, 0 would retire as stale', out.getvalue())
        self.assertFalse(WorldPassage.objects.filter(carried_from__isnull=False).exists())
        call_command('retire_passage', 'test-show-e1', '--carry-forward', '--apply', stdout=out)
        self.assertIn('1 carried forward, 0 retired as stale', out.getvalue())
        self.assertTrue(WorldPassage.objects.filter(carried_from__isnull=False).exists())

    def test_unpublished_episode_is_not_a_world(self):
        with override_settings(ADVENTURE_WORLDS=[{'slug': 'hidden', 'series': 'test-show', 'season': 1, 'episode': 2}]):
            self.assertEqual(self.client.get('/play/hidden/api/state/').status_code, 404)
