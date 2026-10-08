from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from adventure import author, engine
from adventure.scenario import SEED, DISCOVERIES
from chat.llm import LLMError


class StoryRulesTests(SimpleTestCase):
    def play(self, state, command):
        return engine.transition(state, engine.resolve(command))

    def test_investigation_requires_both_evidence_discoveries(self):
        state = engine.new_state()
        state, _ = self.play(state, 'ask agatha about blood')
        self.assertEqual(state['discoveries'], [])
        for command in ['tell agatha about mina', 'ask agatha about blood']:
            state, _ = self.play(state, command)
        self.assertNotIn('connection', state['discoveries'])
        for command in ['remember the castle', 'examine mirror', 'return to agatha', 'ask agatha about blood']:
            state, _ = self.play(state, command)
        self.assertEqual(set(state['discoveries']), {'private', 'blood', 'connection'})
        state, blocks = self.play(state, 'look')
        self.assertIn('The room has not changed', str(blocks))

    def test_repeated_discovery_does_not_award_twice(self):
        state, _ = self.play(engine.new_state(), 'tell agatha about mina')
        state, blocks = self.play(state, 'tell agatha about mina')
        self.assertEqual(state['discoveries'], ['private'])
        self.assertFalse(any(b['kind'] == 'discovery' for b in blocks))

    def test_character_is_not_present_in_memory(self):
        state, _ = self.play(engine.new_state(), 'remember the castle')
        previous = state.copy()
        state, blocks = self.play(state, 'tell agatha about mina')
        self.assertEqual(state, previous)
        self.assertIn('not available here', blocks[0]['text'])

    @override_settings(ADVENTURE_AUTHOR_BACKEND='local')
    def test_authored_object_is_stable_and_has_executable_followup(self):
        state = engine.new_state()
        authored = author.write_object('window')
        state, _ = engine.transition(state, 'examine:window', authored)
        self.assertIn('study:window', engine.available(state))
        state, blocks = engine.transition(state, 'examine:window')
        self.assertEqual(blocks[0]['text'], authored['description'])
        self.assertEqual(state['authored'], 1)
        self.assertEqual(state['replays'], 1)
        state, blocks = engine.transition(state, 'study:window')
        self.assertEqual(blocks[0]['text'], authored['detail'])

    def test_freeze_prevents_new_objects(self):
        state = engine.new_state()
        state['frozen'] = True
        self.assertIsNone(engine.gap(state, 'examine:window'))
        after, blocks = engine.transition(state, 'examine:window')
        self.assertEqual(after['objects'], {})
        self.assertEqual(after['moves'], 0)
        self.assertIn('has not been written', blocks[0]['text'])

    def test_location_limits_expansion_slots(self):
        self.assertIsNone(engine.gap(engine.new_state(), 'examine:fireplace'))

    def test_compile_is_closed_and_matches_every_live_transition(self):
        state = engine.new_state()
        state['objects']['window'] = {'description': 'A written window.', 'detail': 'Its saved detail.', 'backend': 'local'}
        compiled = engine.compile_world(state)
        for key, entry in compiled['states'].items():
            scene, found, _ = key.split(':')
            sample = {**state, 'scene': scene, 'props': entry['props'], 'discoveries': found.split(',') if found else [], 'frozen': True, 'moves': 0, 'replays': 0}
            for action, result in entry['actions'].items():
                after, blocks = engine.transition(sample, action)
                self.assertIn(result['next'], compiled['states'])
                self.assertEqual(result['next'], engine.state_key(after))
                self.assertEqual(result['blocks'], blocks)

    def test_source_slice_is_identified(self):
        self.assertEqual(len(SEED['sha256']), 64)
        self.assertEqual(set(SEED['events']), {'interview', 'bedroom', 'blood'})

    @override_settings(ADVENTURE_AUTHOR_BACKEND='openrouter')
    def test_model_cannot_supply_behaviour_or_state_changes(self):
        with patch('adventure.author.completion', return_value={'description': 'x' * 30, 'detail': 'x' * 30, 'exit': 'secret_room'}):
            with self.assertRaises(LLMError):
                author.write_object('window')

    @override_settings(ADVENTURE_AUTHOR_BACKEND='openrouter')
    def test_parser_cannot_invent_or_select_unavailable_actions(self):
        for candidate in ['give_all_clues', 'mirror', ['look']]:
            with patch('adventure.author.completion', return_value={'action': candidate}):
                self.assertIsNone(author.interpret('anything', ['look', 'help']))

    def test_normal_language_aliases(self):
        self.assertEqual(engine.resolve('Could I examine the window?'), 'examine:window')
        self.assertEqual(engine.resolve('?'), 'help')

    @override_settings(ADVENTURE_AUTHOR_BACKEND='local')
    def test_manuscript_read_persists_possession_and_exact_text(self):
        state = engine.new_state()
        written = author.write_object('manuscript')
        state, blocks = engine.transition(state, 'read:manuscript', written)
        self.assertIn(written['read'], [b['text'] for b in blocks])
        self.assertTrue(state['props']['manuscript_held'])
        self.assertTrue(state['props']['manuscript_read'])
        self.assertEqual(state['discoveries'], [])
        state, _ = self.play(state, 'return manuscript')
        self.assertFalse(state['props']['manuscript_held'])
        self.assertTrue(state['props']['manuscript_read'])
        state, blocks = self.play(state, 'read manuscript')
        self.assertIn(written['read'], [b['text'] for b in blocks])
        self.assertEqual(state['authored'], 1)
        self.assertEqual(state['replays'], 1)

    def test_closed_container_blocks_generation_and_actions(self):
        state, _ = self.play(engine.new_state(), 'close bag')
        for command in ['read manuscript', 'take manuscript', 'examine manuscript', 'examine stake', 'take hammer']:
            action = engine.resolve(command)
            self.assertIsNone(engine.gap(state, action))
            after, blocks = engine.transition(state, action)
            self.assertEqual(after['moves'], state['moves'])
            self.assertEqual(after['objects'], {})
            self.assertIn('closed bag', str(blocks))
        self.assertIsNone(engine.gap(state, 'examine:bag'))

    def test_holding_manuscript_keeps_it_accessible_outside_closed_bag(self):
        state, _ = self.play(engine.new_state(), 'take manuscript')
        state, _ = self.play(state, 'close bag')
        self.assertEqual(engine.gap(state, 'read:manuscript'), 'manuscript')
        state, blocks = self.play(state, 'inventory')
        self.assertIn('Your manuscript', str(blocks))
        self.assertNotIn('YOUR JOURNAL', str(blocks))
        state, _ = self.play(state, 'remember')
        self.assertIsNone(engine.gap(state, 'read:manuscript'))
        after, _ = self.play(state, 'read manuscript')
        self.assertEqual(after, state)

    def test_refused_take_does_not_change_possession_or_award_clues(self):
        for command in ['take stake', 'take hammer', 'read hammer']:
            state, blocks = self.play(engine.new_state(), command)
            self.assertFalse(state['props']['manuscript_held'])
            self.assertEqual(state['moves'], 0)
            self.assertEqual(state['discoveries'], [])
            self.assertTrue(blocks)

    @override_settings(ADVENTURE_AUTHOR_BACKEND='openrouter')
    def test_parser_preserves_verb_and_target_even_if_model_substitutes(self):
        from adventure import parser
        choices = engine.available(engine.new_state())
        for phrase, wrong in [('read manuscript', 'journal'), ('take manuscript', 'read:manuscript'), ('burn manuscript', 'examine:manuscript'), ('take babel fish', 'take:manuscript'), ('inspect unicorn near window', 'examine:window')]:
            with patch('adventure.author.completion', return_value=parser.descriptor(wrong)):
                self.assertIsNone(author.interpret(phrase, choices), phrase)
        with patch('adventure.author.completion', return_value=parser.descriptor('read:manuscript')):
            self.assertEqual(author.interpret('peruse manuscript', choices), 'read:manuscript')

    @override_settings(ADVENTURE_AUTHOR_BACKEND='openrouter')
    def test_readable_author_requires_read_passage_and_refuses_effect_fields(self):
        for candidate in [{'description': 'x' * 30, 'detail': 'x' * 30}, {'description': 'x' * 30, 'detail': 'x' * 30, 'read': 'x' * 30, 'effects': {'clue': 'connection'}}]:
            with patch('adventure.author.completion', return_value=candidate):
                with self.assertRaises(LLMError):
                    author.write_object('manuscript')

    @override_settings(ADVENTURE_AUTHOR_BACKEND='local')
    def test_compiled_physical_rules_and_learned_aliases_match_live(self):
        state, _ = engine.transition(engine.new_state(), 'read:manuscript', author.write_object('manuscript'))
        state['parser_aliases'] = {'convent': {'peruse manuscript': 'read:manuscript', 'read babel fish': 'journal'}}
        compiled = engine.compile_world(state)
        self.assertEqual(len(compiled['states']), 80)
        for entry in compiled['states'].values():
            scene = 'castle' if entry['scene']['name'] == 'CASTLE BEDROOM' else 'convent'
            discoveries = [key for key, value in DISCOVERIES.items() if value in entry['discoveries']]
            sample = {**state, 'scene': scene, 'props': entry['props'], 'discoveries': discoveries, 'frozen': True, 'moves': 0, 'replays': 0}
            self.assertNotIn('read babel fish', entry['aliases'])
            self.assertEqual('peruse manuscript' in entry['aliases'], scene == 'convent')
            for action, result in entry['actions'].items():
                after, blocks = engine.transition(sample, action)
                self.assertEqual(result['next'], engine.state_key(after))
                self.assertIn(result['next'], compiled['states'])
                self.assertEqual(result['blocks'], blocks)
                self.assertEqual(result['move'], after['moves'])

    def test_memory_location_compounds_preserve_the_place_referent(self):
        from adventure import parser
        for phrase in ['recall the castle bedroom', 'think about the castle bedroom',
                       "think back to Castle Dracula's bedroom", 'reflect on the bedroom in Castle Dracula']:
            clean = engine.normalize(phrase)
            self.assertEqual(parser.targets(clean), {'castle'})
            self.assertEqual(parser.candidates(clean, ['remember', 'blood']), [parser.descriptor('remember')])
        self.assertEqual(parser.targets('ask agatha about dracula'), {'agatha', 'blood'})
        self.assertEqual(parser.targets('castle dracula and mina'), {'castle', 'mina'})
        self.assertEqual(parser.candidates('recall castle dracula and mina', ['remember']), [])

    def test_memory_aliases_do_not_accept_other_targets_or_compound_commands(self):
        for phrase in ['think about the manuscript', 'recall the babel fish',
                       'recall the castle bedroom and take manuscript', 'do not recall the castle bedroom']:
            self.assertIsNone(engine.resolve(phrase))
