# Backfill NarrativeConnection.from_episode/to_episode (and correct
# scope) for legacy rows (T-032). The v2.4.0 import writes the
# denormalized episode FKs; legacy (<2.4.0) rows sit at NULL, which
# would drop them from episode-FK-scoped surfaces (connection index,
# event-page within/across split, season bridges). The events' own
# episode FK is the source of truth. On current data every legacy row
# is same-episode (verified in dev), but the scope recompute is kept
# for generality — prod or other legacy DBs may differ.

from django.db import migrations
from django.db.models import F, OuterRef, Q, Subquery


def backfill(apps, schema_editor):
    NarrativeConnection = apps.get_model('narrative', 'NarrativeConnection')
    EventPage = apps.get_model('narrative', 'EventPage')

    # Select rows with EITHER endpoint missing (an asymmetric state can
    # exist after a partial episode deletion); recomputing a
    # already-set FK from its event is a no-op, so setting both is safe.
    NarrativeConnection.objects.filter(
        Q(from_episode__isnull=True) | Q(to_episode__isnull=True)
    ).update(
        from_episode=Subquery(
            EventPage.objects.filter(pk=OuterRef('from_event')).values('episode')[:1]),
        to_episode=Subquery(
            EventPage.objects.filter(pk=OuterRef('to_event')).values('episode')[:1]),
    )
    NarrativeConnection.objects.filter(
        from_episode__isnull=False,
        to_episode__isnull=False,
    ).exclude(from_episode=F('to_episode')).update(scope='cross_episode')


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0025_backfill_storyline_series'),
    ]

    operations = [
        # Reverse is a noop: the backfilled FKs equal the values derived
        # from the events themselves — NULLing them back would only
        # re-break scoped surfaces.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
