"""Shared, durable passages for projected worlds.

Auto-accept: the first passage written for a moment becomes the world's, for
every visitor. Each passage is fingerprinted by the source packet it was
written from; when the record changes, the fingerprint changes and a new
passage is written on next request. Old rows remain as history.
"""
import hashlib
import json

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import narrator
from .models import WorldPassage


def slot_keys(world):
    for event in world['events']:
        yield f"look:{event['uuid']}"
        yield f"watch:{event['uuid']}"
        for part in event['participants']:
            yield f"char:{part['uuid']}@{event['uuid']}"
        for obj in event['objects']:
            yield f"obj:{obj['uuid']}@{event['uuid']}"


def packet_hash(world, key):
    data, _ = narrator.packet(world, key)
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def current_hashes(world):
    """Fingerprint of every passage slot's source, cached on the world dict."""
    if 'hashes' not in world:
        world['hashes'] = {key: packet_hash(world, key) for key in slot_keys(world)}
    return world['hashes']


def live(slug):
    return WorldPassage.objects.filter(world=slug, retired_at__isnull=True)


def as_passage(row):
    return {'text': row.text, 'backend': row.backend, 'sources': row.sources, 'kind': row.kind, 'id': row.pk}


def lookup(slug, world, key, prefer, exact=False):
    """The world's current passage for key: the preferred backend first,
    then (unless exact) any other backend."""
    rows = list(live(slug).filter(key=key, packet_hash=current_hashes(world)[key]).order_by('created_at'))
    for row in rows:
        if row.backend == prefer:
            return as_passage(row)
    if rows and not exact:
        return as_passage(rows[0])
    return None


def save(slug, world, key, passage, playthrough=None):
    """Accept a passage into the world. If another visitor won the race, theirs stands."""
    fingerprint = current_hashes(world)[key]
    try:
        with transaction.atomic():
            row = WorldPassage.objects.create(
                world=slug, key=key, packet_hash=fingerprint, backend=passage['backend'], kind=passage['kind'],
                text=passage['text'], sources=passage['sources'], written_by=playthrough)
    except IntegrityError:
        row = live(slug).get(key=key, packet_hash=fingerprint, backend=passage['backend'])
    return as_passage(row)


def save_rejected(slug, world, key, passage, problems, playthrough=None):
    """Keep a candidate the grounding check refused, already retired, for review."""
    WorldPassage.objects.create(
        world=slug, key=key, packet_hash=current_hashes(world)[key], backend=passage['backend'], kind=passage['kind'],
        text=passage['text'], sources=passage['sources'], written_by=playthrough, retired_at=timezone.now(),
        retired_reason=('grounding: ' + '; '.join(problems))[:300])


def llm_exhausted(slug, world, key):
    """True once this slot's LLM attempts have all been refused for the current record."""
    refused = WorldPassage.objects.filter(world=slug, key=key, packet_hash=current_hashes(world)[key],
                                          backend='openrouter', retired_reason__startswith='grounding')
    return refused.count() >= settings.ADVENTURE_LLM_ATTEMPTS_PER_SLOT


def retire(rows, reason):
    """Retire live rows. They stay as history; the next request writes afresh."""
    return rows.filter(retired_at__isnull=True).update(retired_at=timezone.now(), retired_reason=reason[:300])


def current_rows(slug, world):
    hashes = current_hashes(world)
    return [row for row in live(slug).order_by('created_at') if hashes.get(row.key) == row.packet_hash]


def passages_for(slug, world, prefer):
    """key -> passage for every written slot, preferring one backend. Used by the offline compiler."""
    chosen = {}
    for row in current_rows(slug, world):
        if row.key not in chosen or (row.backend == prefer and chosen[row.key]['backend'] != prefer):
            chosen[row.key] = as_passage(row)
    return chosen


def stats(slug, world):
    rows = current_rows(slug, world)
    return {'written': len({row.key for row in rows}),
            'llm': sum(1 for row in rows if row.backend == 'openrouter'),
            'recent': [(row.key, row.backend) for row in rows[-12:]][::-1]}


def llm_budget_left(slug):
    # Every LLM row cost a call, including retired and refused ones.
    used = WorldPassage.objects.filter(world=slug, backend='openrouter').count()
    return used < settings.ADVENTURE_WORLD_LLM_BUDGET
