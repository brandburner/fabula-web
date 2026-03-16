"""
Data migration to set the Wagtail Site hostname to fabula.productions.

This ensures the sitemap.xml generates https:// URLs with the correct domain.
Only applies in production (when RAILWAY_ENVIRONMENT is set).
"""

import os

from django.db import migrations


def update_site_hostname(apps, schema_editor):
    if not os.environ.get('RAILWAY_ENVIRONMENT'):
        return  # Skip in local dev
    Site = apps.get_model('wagtailcore', 'Site')
    for site in Site.objects.filter(is_default_site=True):
        site.hostname = 'fabula.productions'
        site.port = 443
        site.save()


def revert_site_hostname(apps, schema_editor):
    pass  # No-op; don't revert production hostname


class Migration(migrations.Migration):

    dependencies = [
        ('narrative', '0016_add_season_number_to_episode'),
        ('wagtailcore', '0094_alter_page_locale'),
    ]

    operations = [
        migrations.RunPython(update_site_hostname, revert_site_hostname),
    ]
