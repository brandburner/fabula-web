import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from adventure.models import Playthrough
from chat.llm import LLMError


@override_settings(ADVENTURE_ENABLED=True, ADVENTURE_AUTHOR_BACKEND='local',
                   CHAT_RATE_LIMIT_PER_MINUTE=1000, CHAT_RATE_LIMIT_PER_HOUR=1000)
class StoryAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.state = self.client.get('/play/api/state/').json()

    def command(self, command, request_id=None, version=None):
        response = self.client.post('/play/api/turn/', data=json.dumps({
            'command': command, 'version': self.state['version'] if version is None else version,
            'request_id': request_id or str(uuid.uuid4())}), content_type='application/json')
        if response.status_code == 200:
            self.state = response.json()
        return response

    def test_page_and_embeddable_component(self):
        for url in ['/play/dracula/', '/play/dracula/embed/']:
            response = self.client.get(url)
            self.assertContains(response, 'data-story-terminal')
            self.assertIn('csrftoken', response.cookies)

    def test_save_resumes_with_exact_written_prose(self):
        self.assertEqual(self.command('examine window').status_code, 200)
        saved = self.state
        self.assertEqual(self.client.get('/play/api/state/').json(), saved)
        with patch('adventure.author.write_object', side_effect=AssertionError('must replay')):
            self.command('examine window')
        self.assertEqual(self.state['authored'], 1)
        self.assertEqual(self.state['replays'], 1)

    def test_duplicate_request_is_not_reexecuted_even_after_later_turn(self):
        request_id = str(uuid.uuid4())
        self.command('examine window', request_id=request_id)
        self.command('remember the castle')
        saved = self.state
        with patch('adventure.author.write_object', side_effect=AssertionError('must not author')):
            response = self.command('examine window', request_id=request_id, version=0)
        self.assertEqual(response.json(), saved)
        self.assertEqual(Playthrough.objects.get().turns.count(), 2)

    def test_duplicate_id_with_different_command_is_rejected(self):
        request_id = str(uuid.uuid4())
        self.command('look', request_id=request_id)
        self.assertEqual(self.command('remember', request_id=request_id).status_code, 409)

    def test_stale_version_does_not_overwrite_new_save(self):
        self.command('remember')
        response = self.command('look', version=0)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['state']['scene']['name'], 'CASTLE BEDROOM')

    def test_active_generation_lease_prevents_second_model_call(self):
        Playthrough.objects.update(pending_token=uuid.uuid4(), pending_until=timezone.now() + timedelta(minutes=1))
        with patch('adventure.author.write_object', side_effect=AssertionError('must not author')):
            self.assertEqual(self.command('examine window').status_code, 409)

    def test_expired_generation_lease_can_be_recovered(self):
        Playthrough.objects.update(pending_token=uuid.uuid4(), pending_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.command('examine window').status_code, 200)
        self.assertIsNone(Playthrough.objects.get().pending_token)

    def test_failed_generation_keeps_state_and_releases_lease(self):
        saved = self.state
        with patch('adventure.author.write_object', side_effect=LLMError('provider down')):
            self.assertEqual(self.command('examine window').status_code, 503)
        self.assertEqual(self.client.get('/play/api/state/').json(), saved)
        self.assertIsNone(Playthrough.objects.get().pending_token)
        self.assertEqual(Playthrough.objects.get().turns.count(), 0)

    def test_two_sessions_have_separate_worlds(self):
        self.command('examine window')
        other = Client().get('/play/api/state/').json()
        self.assertNotEqual(other['run_id'], self.state['run_id'])
        self.assertEqual(other['authored'], 0)

    def test_client_cannot_supply_world_state(self):
        response = self.client.post('/play/api/turn/', data=json.dumps({
            'command': 'look', 'request_id': str(uuid.uuid4()), 'version': 0,
            'state': {'discoveries': ['connection']}, 'run_id': str(uuid.uuid4())}), content_type='application/json')
        self.assertEqual(response.json()['discoveries'], [])

    def test_frozen_world_is_playable_without_author(self):
        self.command('freeze world')
        with patch('adventure.author.write_object', side_effect=AssertionError('must not author')):
            for command in ['examine window', 'tell agatha about mina', 'remember', 'examine mirror', 'return', 'ask agatha about blood']:
                self.assertEqual(self.command(command).status_code, 200)
        self.assertEqual(len(self.state['discoveries']), 3)

    def test_restart_preserves_written_game_but_resets_progress(self):
        self.command('examine window')
        self.command('tell agatha about mina')
        self.command('restart story')
        self.assertEqual(self.state['authored'], 1)
        self.assertEqual(self.state['discoveries'], [])
        self.assertEqual(self.state['moves'], 0)

    @override_settings(CHAT_OPENROUTER_API_KEY='test-key')
    def test_live_author_selection_is_saved_and_replay_does_not_call_model(self):
        self.command('use live author')
        self.assertEqual(self.state['author_backend'], 'openrouter')
        with patch('adventure.author.write_object', return_value={
                'description': 'A live-written description.', 'detail': 'An accepted closer look.', 'backend': 'openrouter'}) as write:
            self.command('examine window')
            write.assert_called_once_with('window', selected_backend='openrouter')
        self.assertEqual(self.state['model_calls'], 1)
        with patch('adventure.author.write_object', side_effect=AssertionError('must reuse')):
            self.command('examine window')
        self.assertEqual(self.state['model_calls'], 1)
        self.command('restart story')
        self.assertEqual(self.state['author_backend'], 'openrouter')

    @override_settings(CHAT_OPENROUTER_API_KEY='')
    def test_live_author_not_available_without_key(self):
        self.assertEqual(self.command('use live author').status_code, 503)
        self.assertFalse(self.client.get('/play/api/state/').json()['llm_available'])

    @override_settings(CHAT_OPENROUTER_API_KEY='test-key')
    def test_live_parser_is_disabled_when_frozen(self):
        self.command('use live author')
        self.command('freeze world')
        with patch('adventure.author.interpret', side_effect=AssertionError('must not call parser')):
            self.assertEqual(self.command('invent a spaceship').status_code, 200)

    def test_malformed_payloads(self):
        for payload in [[], {}, {'command': []}, {'command': 'look', 'version': True, 'request_id': str(uuid.uuid4())}]:
            self.assertEqual(self.client.post('/play/api/turn/', data=json.dumps(payload), content_type='application/json').status_code, 400)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/play/api/turn/', data='{}', content_type='application/json').status_code, 403)

    def test_export_is_standalone_and_escapes_authored_script_text(self):
        with patch('adventure.author.write_object', return_value={
                'description': '</script><script>alert(1)</script>', 'detail': 'Written detail', 'backend': 'local'}):
            self.command('examine window')
        response = self.client.get('/play/dracula/download/')
        self.assertContains(response, 'compiled-world')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, '<script src=')
        self.assertNotContains(response, '<link rel="stylesheet"')
        self.assertIn('attachment;', response['Content-Disposition'])

    @override_settings(ADVENTURE_ENABLED=False)
    def test_disabled_routes_are_not_exposed(self):
        for url in ['/play/dracula/', '/play/dracula/embed/', '/play/api/state/', '/play/dracula/download/']:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.command('look').status_code, 404)

    def test_read_manuscript_never_returns_journal_and_survives_reload(self):
        self.command('read manuscript')
        self.assertTrue(self.state['props']['manuscript_read'])
        self.assertTrue(self.state['props']['manuscript_held'])
        self.assertNotIn('YOUR JOURNAL', str(self.state['transcript']))
        self.assertEqual(self.client.get('/play/api/state/').json(), self.state)
        self.command('journal')
        self.assertIn('YOUR JOURNAL', self.state['transcript'][-1]['text'])

    @override_settings(CHAT_OPENROUTER_API_KEY='test-key')
    def test_live_alias_is_saved_reused_frozen_and_exported(self):
        from adventure import parser
        self.command('read manuscript')
        self.command('use live author')
        with patch('adventure.author.completion', return_value=parser.descriptor('read:manuscript')) as model:
            self.command('peruse manuscript')
            self.command('peruse manuscript')
            model.assert_called_once()
        self.assertEqual(self.state['model_calls'], 1)
        self.command('freeze world')
        with patch('adventure.author.completion', side_effect=AssertionError('must replay')):
            self.command('peruse manuscript')
        self.assertContains(self.client.get('/play/dracula/download/'), 'peruse manuscript')
        self.command('restart story')
        self.assertFalse(self.state['props']['manuscript_read'])
        self.assertFalse(self.state['props']['manuscript_held'])
        self.assertEqual(self.state['authored'], 1)
        self.command('peruse manuscript')
        self.assertTrue(self.state['props']['manuscript_read'])
        self.assertEqual(self.state['model_calls'], 1)

    @override_settings(CHAT_OPENROUTER_API_KEY='test-key')
    def test_unknown_target_and_closed_bag_do_not_spend_a_model_call(self):
        self.command('use live author')
        with patch('adventure.author.completion', side_effect=AssertionError('must not call')):
            for command in ['take babel fish', 'burn manuscript', 'close bag', 'read manuscript', 'examine bag']:
                self.assertEqual(self.command(command).status_code, 200)
        self.assertEqual(self.state['model_calls'], 0)
        self.assertFalse(self.state['props']['manuscript_read'])

    def test_older_save_is_upgraded_without_losing_prose_or_discoveries(self):
        self.command('examine bag')
        self.command('tell agatha about mina')
        run = Playthrough.objects.get()
        old_bag = run.state['objects']['bag']
        run.state.pop('props', None)
        run.state.pop('parser_aliases', None)
        run.save()
        self.assertEqual(self.command('read manuscript').status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.state['objects']['bag'], old_bag)
        self.assertEqual(run.state['discoveries'], ['private'])
        self.assertTrue(run.state['props']['manuscript_read'])

    def test_invited_memory_commands_work_without_model_at_any_budget(self):
        phrases = ['think about the castle bedroom', 'recall the castle bedroom',
                   'Could I recall the bedroom?', 'think back to the castle',
                   'remember the bedroom in Castle Dracula']
        for frozen, calls in [(False, 0), (False, 12), (True, 12)]:
            for phrase in phrases:
                with self.subTest(frozen=frozen, calls=calls, phrase=phrase):
                    run = Playthrough.objects.get()
                    run.state.update(scene='convent', frozen=frozen, model_calls=calls, author_backend='openrouter')
                    run.save()
                    with patch('adventure.author.completion', side_effect=AssertionError('memory navigation needs no LLM')):
                        self.assertEqual(self.command(phrase).status_code, 200)
                    self.assertEqual(self.state['scene']['name'], 'CASTLE BEDROOM')
                    self.assertEqual(self.state['model_calls'], calls)
