# Backfill ArcEventMembership/ThemeEventMembership from the legacy bare
# M2M rows (EventPage.arcs / EventPage.themes). role stays null (the M2M
# never carried it — real roles arrive with the v2.4.0 import, T-028);
# episode_ordinal is computed from the event's episode where present.

from django.db import migrations


def backfill(apps, schema_editor):
    EventPage = apps.get_model('narrative', 'EventPage')
    ArcEventMembership = apps.get_model('narrative', 'ArcEventMembership')
    ThemeEventMembership = apps.get_model('narrative', 'ThemeEventMembership')

    arc_rows, theme_rows = [], []
    events = EventPage.objects.select_related('episode').prefetch_related(
        'arcs', 'themes'
    )
    for event in events.iterator(chunk_size=500):
        ordinal = None
        if event.episode_id:
            ordinal = (event.episode.season_number * 100
                       + event.episode.episode_number)
        for arc in event.arcs.all():
            arc_rows.append(ArcEventMembership(
                event=event, arc=arc, role=None, episode_ordinal=ordinal,
            ))
        for theme in event.themes.all():
            theme_rows.append(ThemeEventMembership(
                event=event, theme=theme, episode_ordinal=ordinal,
            ))

    ArcEventMembership.objects.bulk_create(arc_rows, batch_size=500,
                                           ignore_conflicts=True)
    ThemeEventMembership.objects.bulk_create(theme_rows, batch_size=500,
                                             ignore_conflicts=True)


def unbackfill(apps, schema_editor):
    apps.get_model('narrative', 'ArcEventMembership').objects.all().delete()
    apps.get_model('narrative', 'ThemeEventMembership').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0022_conflictarc_involved_characters_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
