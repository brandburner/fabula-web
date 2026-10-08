import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='Playthrough', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('scenario_revision', models.CharField(max_length=40, default='dracula-interview-v1')),
            ('state', models.JSONField(default=dict)),
            ('version', models.PositiveIntegerField(default=0)),
            ('pending_token', models.UUIDField(null=True, blank=True)),
            ('pending_until', models.DateTimeField(null=True, blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='Turn', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('request_id', models.UUIDField()),
            ('command', models.CharField(max_length=300)),
            ('response', models.JSONField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('playthrough', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='turns', to='adventure.playthrough')),
        ]),
        migrations.AddConstraint(model_name='turn', constraint=models.UniqueConstraint(
            fields=('playthrough', 'request_id'), name='adventure_turn_once')),
    ]
