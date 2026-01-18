# Generated manually for megagraph ingestion support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0008_eventpage_global_id_narrativeconnection_global_id'),
    ]

    operations = [
        # CharacterPage megagraph fields
        migrations.AddField(
            model_name='characterpage',
            name='season_appearances',
            field=models.JSONField(blank=True, default=list, help_text='Seasons this character appears in, e.g., [1, 2, 3]'),
        ),
        migrations.AddField(
            model_name='characterpage',
            name='local_uuids',
            field=models.JSONField(blank=True, default=dict, help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"),
        ),
        migrations.AddField(
            model_name='characterpage',
            name='first_appearance_season',
            field=models.PositiveIntegerField(blank=True, help_text='First season this character appears', null=True),
        ),

        # OrganizationPage megagraph fields
        migrations.AddField(
            model_name='organizationpage',
            name='season_appearances',
            field=models.JSONField(blank=True, default=list, help_text='Seasons this organization appears in, e.g., [1, 2, 3]'),
        ),
        migrations.AddField(
            model_name='organizationpage',
            name='local_uuids',
            field=models.JSONField(blank=True, default=dict, help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"),
        ),
        migrations.AddField(
            model_name='organizationpage',
            name='first_appearance_season',
            field=models.PositiveIntegerField(blank=True, help_text='First season this organization appears', null=True),
        ),

        # ObjectPage megagraph fields
        migrations.AddField(
            model_name='objectpage',
            name='season_appearances',
            field=models.JSONField(blank=True, default=list, help_text='Seasons this object appears in, e.g., [1, 2, 3]'),
        ),
        migrations.AddField(
            model_name='objectpage',
            name='local_uuids',
            field=models.JSONField(blank=True, default=dict, help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"),
        ),
        migrations.AddField(
            model_name='objectpage',
            name='first_appearance_season',
            field=models.PositiveIntegerField(blank=True, help_text='First season this object appears', null=True),
        ),

        # Location (snippet) megagraph fields
        migrations.AddField(
            model_name='location',
            name='season_appearances',
            field=models.JSONField(blank=True, default=list, help_text='Seasons this entity appears in, e.g., [1, 2, 3]'),
        ),
        migrations.AddField(
            model_name='location',
            name='local_uuids',
            field=models.JSONField(blank=True, default=dict, help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"),
        ),
        migrations.AddField(
            model_name='location',
            name='first_appearance_season',
            field=models.PositiveIntegerField(blank=True, help_text='First season this entity appears', null=True),
        ),

        # EventPage megagraph source tracking fields
        migrations.AddField(
            model_name='eventpage',
            name='source_season',
            field=models.PositiveIntegerField(blank=True, help_text='Season number this event came from (for megagraph imports)', null=True),
        ),
        migrations.AddField(
            model_name='eventpage',
            name='source_database',
            field=models.CharField(blank=True, help_text='Source database name, e.g., westwing.s01', max_length=100),
        ),
    ]
