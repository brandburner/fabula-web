"""
Ask the Archive — stateless chat endpoint.

POST /api/chat/            SSE stream, typed events:
                           content / tool_start / rich_links / followups /
                           metadata / error / [DONE]
GET  /api/chat/suggestions/ deterministic welcome chips (no LLM)

Stateless per the ported design: the client resends trimmed history and the
sanitized tool_context each turn. CSRF-exempt is deliberate — anonymous
public endpoint, no auth cookies to ride, rate-limited per IP.
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from narrative.models import EpisodePage, SeriesIndexPage

from .chips import followup_chips, welcome_chips
from .llm import LLMError, get_llm_client
from .prompts import build_messages
from .ratelimit import check_rate_limit
from .rich_links import extract_rich_links
from .sanitize import BadPayload, build_tool_context, parse_chat_payload
from .tool_loop import run_chat_turn

logger = logging.getLogger(__name__)


def _sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


def _resolve_series(slug):
    """Validate the client-sent series slug; fall back to first live series."""
    series = None
    if slug:
        series = SeriesIndexPage.objects.live().filter(slug=slug).first()
    if series is None:
        series = SeriesIndexPage.objects.live().first()
    return series


@csrf_exempt
@require_POST
def chat_stream(request):
    if not settings.CHAT_ENABLED:
        return JsonResponse(
            {'error': 'Chat is not enabled on this deployment.'}, status=503)

    allowed, retry_after = check_rate_limit(request)
    if not allowed:
        response = JsonResponse(
            {'error': 'Rate limit exceeded — the archivist needs a '
                      'breather. Try again shortly.'}, status=429)
        response['Retry-After'] = str(retry_after)
        return response

    try:
        payload = parse_chat_payload(request)
    except BadPayload as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    series = _resolve_series(payload['series'])
    if series is None:
        return JsonResponse(
            {'error': 'The archive holds no series yet.'}, status=503)

    seasons = sorted(set(
        EpisodePage.objects.live().descendant_of(series)
        .values_list('season_number', flat=True)))

    messages = build_messages(
        payload['message'],
        payload['history'],
        series.slug,
        page_context=payload['page_context'],
        tool_context=payload['tool_context'],
    )

    try:
        client = get_llm_client()
    except LLMError as exc:
        logger.error('chat: client init failed: %s', exc)
        return JsonResponse({'error': exc.friendly}, status=503)

    def event_stream():
        try:
            for event in run_chat_turn(
                    client, messages,
                    series_slug=series.slug,
                    series_title=series.title,
                    seasons=seasons):
                if event['event'] == 'content':
                    yield _sse('content', {'text': event['text']})
                elif event['event'] == 'tool_start':
                    yield _sse('tool_start', {'tool': event['tool'],
                                              'args': event['args']})
                elif event['event'] == 'turn_complete':
                    collected = event['collected']
                    cards = extract_rich_links(collected)
                    if cards:
                        yield _sse('rich_links', {'links': cards})
                    chips = followup_chips(collected, event['final_text'])
                    if chips:
                        yield _sse('followups', {'chips': chips})
                    yield _sse('metadata', {
                        'series': series.slug,
                        'fallback': event['fallback'],
                        'tool_calls': len(collected),
                        'tool_context': build_tool_context(collected),
                    })
        except LLMError as exc:
            logger.error('chat: LLM error mid-stream: %s', exc)
            yield _sse('error', {'message': exc.friendly})
        except Exception:
            logger.exception('chat: unexpected error mid-stream')
            yield _sse('error', {
                'message': 'Something went wrong on our side. '
                           'Please try again.'})
        yield 'data: [DONE]\n\n'

    response = StreamingHttpResponse(
        event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@require_GET
def chat_suggestions(request):
    if not settings.CHAT_ENABLED:
        return JsonResponse({'chips': []})
    chips = welcome_chips(
        request.GET.get('page_type', ''),
        entity_name=request.GET.get('entity_name', '')[:200] or None,
        series_slug=request.GET.get('series', '')[:100] or None,
    )
    return JsonResponse({'chips': chips})
