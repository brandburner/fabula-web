# Backfill Theme.series / ConflictArc.series for legacy rows (ISS-015).
# The v2.4.0 import sets the FK from the export's series_uuid, but the
# legacy (<2.4.0) path never did — westwing's storylines all sit at NULL.
# Series is inferred from membership evidence: the most common series
# among a storyline's member events (matched by page-tree path prefix,
# the same Counter fallback the exporter uses). Storylines with no
# member events stay NULL.

from collections import Counter

from django.db import migrations


def backfill(apps, schema_editor):
    Page = apps.get_model('wagtailcore', 'Page')
    SeriesIndexPage = apps.get_model('narrative', 'SeriesIndexPage')
    Theme = apps.get_model('narrative', 'Theme')
    ConflictArc = apps.get_model('narrative', 'ConflictArc')
    ArcEventMembership = apps.get_model('narrative', 'ArcEventMembership')
    ThemeEventMembership = apps.get_model('narrative', 'ThemeEventMembership')

    series_paths = dict(
        Page.objects.filter(
            id__in=SeriesIndexPage.objects.values('page_ptr_id')
        ).values_list('id', 'path')
    )
    if not series_paths:
        return

    targets = [
        (Theme, ThemeEventMembership, 'theme_id'),
        (ConflictArc, ArcEventMembership, 'arc_id'),
    ]
    for model, membership_model, fk in targets:
        for snippet in model.objects.filter(series__isnull=True):
            event_ids = membership_model.objects.filter(
                **{fk: snippet.pk}
            ).values_list('event_id', flat=True)
            event_paths = Page.objects.filter(
                id__in=list(event_ids)
            ).values_list('path', flat=True)

            counts = Counter()
            for path in event_paths:
                for series_id, series_path in series_paths.items():
                    if path.startswith(series_path):
                        counts[series_id] += 1
            if counts:
                snippet.series_id = counts.most_common(1)[0][0]
                snippet.save(update_fields=['series'])


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0024_characterpage_arc_summary_characterseasonprofile'),
        ('wagtailcore', '0001_initial'),
    ]

    operations = [
        # Reverse is a noop: backfilled FKs are indistinguishable from
        # import-set ones, and NULLing them back would break scoping.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
