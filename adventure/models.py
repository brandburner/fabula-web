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
