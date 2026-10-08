import copy
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from chat.llm import LLMError
from chat.ratelimit import check_rate_limit
from . import author, scenarios
from .models import Playthrough, Turn


def enabled(slug):
    if not settings.ADVENTURE_ENABLED:
        raise Http404
    return scenarios.get(slug)


def current_run(request, scenario):
    run_id = request.session.get(scenario.session_key)
    run = Playthrough.objects.filter(pk=run_id).first() if run_id else None
    if run is None:
        run = Playthrough.objects.create(state=scenario.new_state(), scenario_revision=scenario.revision)
        request.session[scenario.session_key] = str(run.pk)
    if run.scenario_revision != scenario.revision:
        raise Http404('This prototype save belongs to a different scenario revision.')
    return run


def snapshot(run, scenario):
    result = scenario.public_state(run.state, run.version, run.pk,
                                   run.state.get('author_backend', author.backend()))
    result['llm_available'] = bool(settings.CHAT_OPENROUTER_API_KEY)
    return result


class AuthorBudgetExceeded(Exception):
    pass


def prepare(run, command, scenario):
    proposed = copy.deepcopy(run.state)
    clean = scenario_normalize(command)
    calls = 0
    mode = proposed.get('author_backend', author.backend())
    if clean in ('use live author', 'use local author'):
        if clean == 'use live author' and not settings.CHAT_OPENROUTER_API_KEY:
            raise LLMError('No author key is configured.')
        proposed['author_backend'] = 'openrouter' if clean == 'use live author' else 'local'
        blocks = [block('Live LLM author selected. New passages and unfamiliar command interpretation use the configured OpenRouter key. Existing passages are still replayed.' if clean == 'use live author' else 'Local author selected. New passages use the source record directly; no model calls.', 'system')]
    elif clean in ('freeze world', 'enable author'):
        proposed['frozen'] = clean == 'freeze world'
        blocks = [block('World frozen. Every written passage now runs without an author.' if proposed['frozen'] else 'Author enabled. Unwritten passages can be filled in as you explore.', 'system')]
    elif clean == 'restart story':
        proposed = scenario.restart(proposed)
        proposed['author_backend'] = mode
        blocks = []
    else:
        status, payload = scenario.resolve(command, proposed)
        action = payload if status == 'action' else None
        if (action is None and status == 'unknown' and not proposed['frozen'] and mode == 'openrouter'
                and proposed['model_calls'] < 12):
            choices = scenario.candidates(clean, proposed)
            if choices:
                calls += 1
                action = author.choose(clean, choices, selected_backend=mode)
        if calls and action is not None:
            # Dracula scopes learned phrases per scene; projected worlds scope them per world.
            if scenario.slug == 'dracula':
                proposed.setdefault('parser_aliases', {}).setdefault(proposed['scene'], {})[clean] = action
            else:
                proposed.setdefault('parser_aliases', {})[clean] = action
        slot = scenario.gap(proposed, action) if action else None
        written = None
        if slot:
            if mode == 'openrouter' and scenario.budget_exceeded(proposed, calls):
                raise AuthorBudgetExceeded
            written = scenario.write(slot, proposed, mode, run)
            calls += int(mode == 'openrouter')
        if action is None:
            blocks = scenario.refusal(proposed, status, payload, clean)
        else:
            proposed, blocks = scenario.transition(proposed, action, written)
    proposed['model_calls'] += calls
    if clean != 'restart story':
        proposed['transcript'] += [block(command, 'command'), *blocks]
    proposed['transcript'] = proposed['transcript'][-300:]
    return proposed, blocks


def block(text, kind='narration'):
    return {'text': text, 'kind': kind}


def scenario_normalize(command):
    from .engine import normalize
    return normalize(command)


def page_context(scenario, embedded):
    return {'embedded': embedded, 'scenario': scenario, 'meta': scenario.meta,
            'api_base': '/play/api/' if scenario.slug == 'dracula' else f'/play/{scenario.slug}/api/',
            'download_url': f'/play/{scenario.slug}/download/'}


@never_cache
@ensure_csrf_cookie
@require_GET
def play(request, slug='dracula'):
    scenario = enabled(slug)
    return render(request, 'adventure/play.html', page_context(scenario, False))


@never_cache
@ensure_csrf_cookie
@require_GET
def embed(request, slug='dracula'):
    scenario = enabled(slug)
    return render(request, 'adventure/embed.html', page_context(scenario, True))


@never_cache
@require_GET
def state(request, slug='dracula'):
    scenario = enabled(slug)
    return JsonResponse(snapshot(current_run(request, scenario), scenario))


@never_cache
@require_POST
def turn(request, slug='dracula'):
    scenario = enabled(slug)
    if len(request.body) > 4096:
        return JsonResponse({'error': 'Command request is too large.'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        command = data['command']
        version = data['version']
        request_id = uuid.UUID(data['request_id'])
        if (not isinstance(command, str) or not command.strip() or len(command) > 300
                or type(version) is not int or version < 0):
            raise ValueError
        command = command.strip()
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeDecodeError):
        return JsonResponse({'error': 'A command, state version and request ID are required.'}, status=400)
    run = current_run(request, scenario)
    receipt = run.turns.filter(request_id=request_id).first()
    if receipt:
        if receipt.command != command:
            return JsonResponse({'error': 'This request ID belongs to another command.'}, status=409)
        # Return current authoritative state, never roll a client back to an
        # old receipt. The command is not executed or billed again.
        return JsonResponse(snapshot(run, scenario))
    if run.version != version:
        return JsonResponse({'error': 'Your story advanced in another tab. The latest save is loaded.', 'state': snapshot(run, scenario)}, status=409)
    allowed, retry = check_rate_limit(request)
    if not allowed:
        response = JsonResponse({'error': 'A moment, please. Try this command again shortly.'}, status=429)
        response['Retry-After'] = str(retry)
        return response
    if run.version >= 500:
        return JsonResponse({'error': 'This prototype save has reached its turn limit. You can still download it.'}, status=429)
    # A short database lease prevents concurrent retries from paying for
    # the same generation twice. No transaction stays open during the LLM.
    token = uuid.uuid4()
    with transaction.atomic():
        locked = Playthrough.objects.select_for_update().get(pk=run.pk)
        receipt = Turn.objects.filter(playthrough=locked, request_id=request_id).first()
        if receipt:
            if receipt.command != command:
                return JsonResponse({'error': 'This request ID belongs to another command.'}, status=409)
            return JsonResponse(snapshot(locked, scenario))
        if locked.version != version:
            return JsonResponse({'error': 'The latest save is loaded. Try your command again.', 'state': snapshot(locked, scenario)}, status=409)
        if locked.pending_until and locked.pending_until > timezone.now():
            return JsonResponse({'error': 'Another action is being written. Wait a moment, then retry.'}, status=409)
        locked.pending_token = token
        locked.pending_until = timezone.now() + timedelta(minutes=5)
        locked.save(update_fields=['pending_token', 'pending_until'])
    try:
        try:
            proposed, blocks = prepare(locked, command, scenario)
        except LLMError:
            return JsonResponse({'error': 'The author could not finish this passage. Your position is unchanged; retry or freeze the world.'}, status=503)
        except AuthorBudgetExceeded:
            return JsonResponse({'error': 'The author budget is used up. Freeze and play the written world, or switch to the local author.'}, status=429)
        with transaction.atomic():
            locked = Playthrough.objects.select_for_update().get(pk=run.pk)
            if locked.version != version or locked.pending_token != token:
                return JsonResponse({'error': 'The latest save is loaded. Try your command again.', 'state': snapshot(locked, scenario)}, status=409)
            locked.state = proposed
            locked.version += 1
            locked.pending_token = None
            locked.pending_until = None
            locked.save(update_fields=['state', 'version', 'updated_at', 'pending_token', 'pending_until'])
            Turn.objects.create(playthrough=locked, request_id=request_id, command=command,
                                response={'version': locked.version, 'blocks': blocks})
        return JsonResponse(snapshot(locked, scenario))
    finally:
        Playthrough.objects.filter(pk=run.pk, pending_token=token).update(pending_token=None, pending_until=None)


@never_cache
@require_GET
def export(request, slug='dracula'):
    scenario = enabled(slug)
    run = current_run(request, scenario)
    compiled = scenario.compile_world(run.state)
    compiled['export_id'] = str(run.pk)
    # Inline only our own static assets; json_script safely escapes content.
    root = settings.BASE_DIR / 'static' / 'adventure'
    html = render_to_string('adventure/offline.html', {
        **page_context(scenario, True), 'compiled': compiled,
        'css': (root / 'terminal.css').read_text(),
        'js': (root / 'terminal.js').read_text(),
    })
    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{scenario.meta["filename"]}"'
    return response
