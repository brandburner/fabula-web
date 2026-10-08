"""Loop-guard behaviors, driven by a scripted LLM client — no network."""

from chat.tool_loop import (
    MAX_TOOL_ITERATIONS,
    run_chat_turn,
)

from .base import NarrativeGraphTestCase


class ScriptedClient:
    """Yields pre-programmed turns; repeats the last one forever."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def stream_completion(self, messages, tools=None):
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        if callable(turn):
            turn = turn(self.calls)
        content = turn.get('content', '')
        if content:
            yield {'kind': 'delta', 'text': content}
        yield {'kind': 'final', 'content': content,
               'tool_calls': turn.get('tool_calls', [])}


def tool_call(name, args, call_id='c1'):
    return {'id': call_id, 'name': name, 'arguments': args}


def drain(client, messages=None):
    return list(run_chat_turn(
        client, messages or [{'role': 'user', 'content': 'hi'}],
        series_slug='alpha-show', series_title='Alpha Show', seasons=[1]))


class LoopTests(NarrativeGraphTestCase):
    def test_tool_then_answer(self):
        client = ScriptedClient([
            {'tool_calls': [tool_call('graph_stats',
                                      {'series': 'alpha-show'})]},
            {'content': 'The archive holds 3 events.'},
        ])
        events = drain(client)
        kinds = [e['event'] for e in events]
        self.assertEqual(kinds,
                         ['tool_start', 'content', 'turn_complete'])
        done = events[-1]
        self.assertFalse(done['fallback'])
        self.assertEqual(len(done['collected']), 1)
        self.assertEqual(done['final_text'], 'The archive holds 3 events.')

    def test_same_turn_dedup(self):
        call = tool_call('graph_stats', {'series': 'alpha-show'})
        client = ScriptedClient([
            {'tool_calls': [call]},
            {'tool_calls': [dict(call, id='c2')]},  # identical (tool, args)
            {'content': 'Done.'},
        ])
        events = drain(client)
        done = events[-1]
        # Second identical call served from cache: executed exactly once.
        self.assertEqual(len(done['collected']), 1)
        self.assertEqual(
            len([e for e in events if e['event'] == 'tool_start']), 1)

    def test_empty_streak_early_exit_with_fallback(self):
        client = ScriptedClient([
            lambda n: {'tool_calls': [tool_call(
                'resolve_entity',
                {'series': 'alpha-show', 'query': f'Zorblax {n}'})]},
        ])
        events = drain(client)
        done = events[-1]
        self.assertTrue(done['fallback'])
        self.assertIn('Alpha Show', done['final_text'])
        # Two empty iterations, then out — not eight.
        self.assertEqual(len(done['collected']), 2)

    def test_iteration_cap_forces_fallback(self):
        client = ScriptedClient([
            lambda n: {'tool_calls': [tool_call(
                'character_timeline',
                {'series': 'alpha-show', 'character': 'Alice Alpha',
                 'limit': n})]},  # unique args: never deduped, never empty
        ])
        events = drain(client)
        done = events[-1]
        self.assertTrue(done['fallback'])
        self.assertEqual(len(done['collected']), MAX_TOOL_ITERATIONS)

    def test_stalled_model_falls_back(self):
        client = ScriptedClient([{'content': ''}])
        events = drain(client)
        self.assertTrue(events[-1]['fallback'])
