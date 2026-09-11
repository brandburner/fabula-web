"""
Data repair for UP-012 / ISS-032: locations whose parent_location is
themselves. The megagraph location-hierarchy step emitted PART_OF self-loops,
the exporter passed them through as parent_location_uuid == own uuid, and the
importer set them. Prod carried 182 such rows on 2026-09-11, each rendering as
a schema.org Place containedInPlace itself. The importer now refuses the row;
this clears what is already stored.
"""

from django.db import migrations
from django.db.models import F


def clear_self_parents(apps, schema_editor):
    Location = apps.get_model('narrative', 'Location')
    Location.objects.filter(parent_location_id=F('pk')).update(parent_location=None)


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0027_characteraffiliation'),
    ]

    operations = [
        migrations.RunPython(clear_self_parents, migrations.RunPython.noop),
    ]
