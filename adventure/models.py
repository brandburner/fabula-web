import uuid

from django.db import models


class Playthrough(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_revision = models.CharField(max_length=40, default='dracula-interview-v1')
    state = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    pending_token = models.UUIDField(null=True, blank=True)
    pending_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Turn(models.Model):
    playthrough = models.ForeignKey(Playthrough, on_delete=models.CASCADE, related_name='turns')
    request_id = models.UUIDField()
    command = models.CharField(max_length=300)
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['playthrough', 'request_id'], name='adventure_turn_once')]


class WorldPassage(models.Model):
    """An accepted passage that belongs to a projected world, not to one visitor.

    The first accepted passage for (world, key, packet_hash, backend) serves
    every later visitor. packet_hash fingerprints the source record the
    passage was written from, so a changed record yields a new hash and the
    old passage simply stops matching: it is retired, not overwritten.
    """
    world = models.CharField(max_length=64)
    key = models.CharField(max_length=200)
    packet_hash = models.CharField(max_length=64)
    backend = models.CharField(max_length=20)
    kind = models.CharField(max_length=20)
    text = models.TextField()
    sources = models.JSONField(default=list)
    written_by = models.ForeignKey(Playthrough, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='world_passages')
    created_at = models.DateTimeField(auto_now_add=True)
    # A retired passage no longer serves anyone; the next request writes a new
    # one. Rows rejected by the grounding check are stored already retired.
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_reason = models.CharField(max_length=300, blank=True)
    # Set when this row re-uses an earlier passage that still passed the
    # grounding check after its record changed. A carried row cost no call.
    carried_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='carried_to')

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['world', 'key', 'packet_hash', 'backend'], condition=models.Q(retired_at__isnull=True),
            name='adventure_world_passage_live_once')]
        indexes = [models.Index(fields=['world', 'key'], name='adventure_world_key')]
