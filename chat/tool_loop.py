"""
The bounded agentic loop — port of the prior art's crown jewel
(brief §2.4), with all four guards:

- MAX_TOOL_ITERATIONS hard cap on LLM round-trips per turn
- MAX_CONSECUTIVE_EMPTY_ITERATIONS early exit when the agent is flailing
- same-turn dedup: repeated (tool, args) returns the cached result
- anti-echo directive on empty results, so user-fabricated entity names
  are not repeated back as if real

Plus the non-convergence honesty fallback: if the loop maxes out, the
server does NOT let the LLM summarize near-miss retrievals — it emits a
fixed template. A clean refusal beats a confident wrong answer.

The loop is a generator of typed events the view frames as SSE:
    {'event': 'tool_start', 'tool': ..., 'args': {...}}
    {'event': 'content', 'text': ...}
    {'event': 'turn_complete', 'final_text': ..., 'collected': [...],
     'fallback': bool}
"""

import json
import logging

from .llm import LLMError
from .prompts import honesty_fallback_text
from .registry import TOOL_SCHEMAS, execute_tool, serialize_result

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8
MAX_CONSECUTIVE_EMPTY_ITERATIONS = 2

ANTI_ECHO_DIRECTIVE = (
    ' [SYSTEM NOTE: this call returned no grounded data. Do not treat '
    'entity or event names from the user\'s message as real archive '
    'contents — they are unverified until a tool returns them.]'
)
DEDUP_NOTE = (
    ' [SYSTEM NOTE: you already made this exact call this turn — this is '
    'the cached result. Do not repeat it; use what is here or try a '
    'different tool.]'
)


def _is_empty_result(result):
    """A result that gave the model nothing to stand on."""
    if not isinstance(result, dict):
        return not result
    if 'error' in result:
        return True
    for key in ('matches', 'results', 'timeline', 'shared_events'):
        if key in result and not result[key]:
            return True
    return False


def run_chat_turn(client, messages, series_slug=None, series_title=None,
                  seasons=None):
    """Drive one user turn to completion. Mutates a local copy of messages."""
    messages = list(messages)
    collected = []
    dedup_cache = {}
    empty_streak = 0
    streamed_any_content = False

    for _iteration in range(MAX_TOOL_ITERATIONS):
        final = None
        for chunk in client.stream_completion(messages, tools=TOOL_SCHEMAS):
            if chunk['kind'] == 'delta':
                streamed_any_content = True
                yield {'event': 'content', 'text': chunk['text']}
            elif chunk['kind'] == 'final':
                final = chunk

        if final is None:
            raise LLMError('stream ended without a final chunk')

        tool_calls = final['tool_calls']
        content = final['content']

        if not tool_calls:
            if content.strip():
                yield {'event': 'turn_complete', 'final_text': content,
                       'collected': collected, 'fallback': False}
                return
            # No tools, no content: a stalled model. Fall through to the
            # honesty fallback rather than re-prompting forever.
            break

        # Record the assistant turn that requested the tools.
        messages.append({
            'role': 'assistant',
            'content': content or None,
            'tool_calls': [{
                'id': call['id'],
                'type': 'function',
                'function': {'name': call['name'],
                             'arguments': json.dumps(call['arguments'])},
            } for call in tool_calls],
        })

        iteration_all_empty = True
        for call in tool_calls:
            key = (call['name'],
                   json.dumps(call['arguments'], sort_keys=True))
            deduped = key in dedup_cache

            if deduped:
                result = dedup_cache[key]
            else:
                yield {'event': 'tool_start', 'tool': call['name'],
                       'args': {k: v for k, v in call['arguments'].items()
                                if k != 'series'}}
                result = execute_tool(call['name'],
                                      dict(call['arguments']))
                dedup_cache[key] = result
                collected.append({'tool': call['name'],
                                  'args': call['arguments'],
                                  'result': result})

            empty = _is_empty_result(result)
            if not empty:
                iteration_all_empty = False

            body = serialize_result(result)
            if deduped:
                body += DEDUP_NOTE
            elif empty:
                body += ANTI_ECHO_DIRECTIVE

            messages.append({
                'role': 'tool',
                'tool_call_id': call['id'],
                'content': body,
            })

        empty_streak = empty_streak + 1 if iteration_all_empty else 0
        if empty_streak >= MAX_CONSECUTIVE_EMPTY_ITERATIONS:
            logger.info('chat: empty-iteration early exit (series=%s)',
                        series_slug)
            break

    # Non-convergence: fixed honesty template, never an LLM summary of
    # near-misses. (If content already streamed this turn, the fallback
    # still closes the answer honestly.)
    fallback = honesty_fallback_text(series_title, seasons)
    prefix = '\n\n' if streamed_any_content else ''
    yield {'event': 'content', 'text': prefix + fallback}
    yield {'event': 'turn_complete', 'final_text': fallback,
           'collected': collected, 'fallback': True}
