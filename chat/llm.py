"""
LLM transport for Ask the Archive.

OpenRouter chat-completions with function calling, streamed. The client
yields typed dicts so the tool loop never touches wire format:

    {'kind': 'delta', 'text': '...'}          # content token(s), live
    {'kind': 'final', 'content': '...', 'tool_calls': [...]}  # end of turn

A scripted FakeLLMClient (CHAT_LLM_BACKEND=fake) drives the whole pipeline
without an API key — used by tests and for local widget development.
"""

import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 90


class LLMError(Exception):
    """Transport-level failure with a user-safe message."""

    def __init__(self, message, friendly=None):
        super().__init__(message)
        self.friendly = friendly or (
            'The archivist is unavailable right now. Please try again in a '
            'few minutes.')


class LLMOverCapacity(LLMError):
    def __init__(self, message):
        super().__init__(message, friendly=(
            "The archive is over capacity at the moment — too many "
            "conversations at once. Please try again shortly."))


class OpenRouterClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or settings.CHAT_OPENROUTER_API_KEY
        self.model = model or settings.CHAT_MODEL
        if not self.api_key:
            raise LLMError('CHAT: no OpenRouter API key configured')

    def stream_completion(self, messages, tools=None):
        payload = {
            'model': self.model,
            'messages': messages,
            'stream': True,
            'max_tokens': settings.CHAT_MAX_TOKENS,
            'temperature': settings.CHAT_TEMPERATURE,
        }
        if tools:
            payload['tools'] = tools

        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://fabula.productions',
                    # Header values must be latin-1 — no em dashes here.
                    'X-Title': 'Fabula - Ask the Archive',
                },
                json=payload,
                stream=True,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.RequestException as exc:
            raise LLMError(f'OpenRouter request failed: {exc}') from exc

        if response.status_code in (402, 429):
            raise LLMOverCapacity(
                f'OpenRouter returned {response.status_code}')
        if response.status_code != 200:
            body = response.text[:500]
            raise LLMError(
                f'OpenRouter returned {response.status_code}: {body}')

        content_parts = []
        # index -> {'id': ..., 'name': ..., 'arguments': str}
        tool_calls = {}

        # OpenRouter streams text/event-stream without a charset; requests then
        # guesses ISO-8859-1 and curly quotes arrive as mojibake. SSE is UTF-8.
        response.encoding = 'utf-8'
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith('data:'):
                continue
            data = raw_line[len('data:'):].strip()
            if data == '[DONE]':
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get('choices') or []
            if not choices:
                continue
            delta = choices[0].get('delta') or {}

            text = delta.get('content')
            if text:
                content_parts.append(text)
                yield {'kind': 'delta', 'text': text}

            for fragment in delta.get('tool_calls') or []:
                idx = fragment.get('index', 0)
                slot = tool_calls.setdefault(
                    idx, {'id': None, 'name': None, 'arguments': ''})
                if fragment.get('id'):
                    slot['id'] = fragment['id']
                fn = fragment.get('function') or {}
                if fn.get('name'):
                    slot['name'] = fn['name']
                if fn.get('arguments'):
                    slot['arguments'] += fn['arguments']

        calls = []
        for idx in sorted(tool_calls):
            slot = tool_calls[idx]
            if not slot['name']:
                continue
            try:
                args = json.loads(slot['arguments'] or '{}')
            except json.JSONDecodeError:
                args = {'_malformed': slot['arguments'][:500]}
            calls.append({
                'id': slot['id'] or f'call_{idx}',
                'name': slot['name'],
                'arguments': args,
            })

        yield {'kind': 'final',
               'content': ''.join(content_parts),
               'tool_calls': calls}


class FakeLLMClient:
    """Deterministic scripted backend: one graph_stats call, then a summary.

    Exercises the full pipeline (tool execution, rich links, chips, SSE,
    widget) with zero LLM dependency. Selected via CHAT_LLM_BACKEND=fake.
    """

    def __init__(self, series_slug='wolf-hall'):
        self.series_slug = series_slug

    def stream_completion(self, messages, tools=None):
        # Series hint is injected into the system message as
        # "Active series: <slug>" — mirror a real model reading its context.
        for message in messages:
            if message['role'] == 'system':
                for line in str(message.get('content', '')).splitlines():
                    if line.startswith('Active series:'):
                        slug = line.split(':', 1)[1].strip()
                        if slug:
                            self.series_slug = slug

        already_called = any(m['role'] == 'tool' for m in messages)
        if not already_called:
            yield {'kind': 'final', 'content': '', 'tool_calls': [{
                'id': 'call_fake_1',
                'name': 'graph_stats',
                'arguments': {'series': self.series_slug},
            }]}
            return

        last_tool = next(
            m for m in reversed(messages) if m['role'] == 'tool')
        try:
            stats = json.loads(last_tool['content'])
        except (json.JSONDecodeError, TypeError):
            stats = {}
        text = (
            f"[fake backend] The archive holds **{stats.get('events', '?')} "
            f"events** and **{stats.get('connections_total', '?')} "
            f"connections** for {stats.get('series', self.series_slug)}. "
            f"Configure OPENROUTER_API_KEY to talk to the real archivist."
        )
        for i in range(0, len(text), 40):
            yield {'kind': 'delta', 'text': text[i:i + 40]}
        yield {'kind': 'final', 'content': text, 'tool_calls': []}


def get_llm_client():
    if settings.CHAT_LLM_BACKEND == 'fake':
        return FakeLLMClient()
    return OpenRouterClient()
