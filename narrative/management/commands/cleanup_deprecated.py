"""
Management command to remove deprecated entities that are no longer in the YAML export.

When the Neo4j export filters out deprecated entities (status != 'canonical'),
those entities may still exist in the Wagtail database from previous imports.
This command identifies and removes them.

Usage:
    python manage.py cleanup_deprecated ./fabula_export --dry-run
    python manage.py cleanup_deprecated ./fabula_export
"""

from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from narrative.models import (
    CharacterPage,
    OrganizationPage,
    Location,
)


class Command(BaseCommand):
    help = 'Remove deprecated entities not present in the current YAML export'

    def add_arguments(self, parser):
        parser.add_argument(
            'export_dir',
            type=str,
            help='Path to the YAML export directory'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        export_dir = Path(options['export_dir'])
        dry_run = options['dry_run']

        if not export_dir.exists():
            raise CommandError(f'Export directory not found: {export_dir}')

        self.stdout.write(f"\n{'DRY RUN - ' if dry_run else ''}Cleanup Deprecated Entities")
        self.stdout.write("=" * 60)

        total_deleted = 0

        # Cleanup Characters
        characters_file = export_dir / 'characters.yaml'
        if characters_file.exists():
            deleted = self.cleanup_model(
                characters_file,
                CharacterPage,
                'fabula_uuid',
                dry_run
            )
            total_deleted += deleted

        # Cleanup Organizations
        orgs_file = export_dir / 'organizations.yaml'
        if orgs_file.exists():
            deleted = self.cleanup_model(
                orgs_file,
                OrganizationPage,
                'fabula_uuid',
                dry_run
            )
            total_deleted += deleted

        # Cleanup Locations (snippet, not page)
        locations_file = export_dir / 'locations.yaml'
        if locations_file.exists():
            deleted = self.cleanup_snippet(
                locations_file,
                Location,
                'fabula_uuid',
                dry_run
            )
            total_deleted += deleted

        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would delete {total_deleted} deprecated entities'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {total_deleted} deprecated entities'
            ))

    def cleanup_model(self, yaml_file, model_class, uuid_field, dry_run):
        """Cleanup a Wagtail Page model."""
        model_name = model_class.__name__

        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f) or []

        # Handle both list format and dict with key format
        if isinstance(data, dict):
            # Try common keys
            for key in ['characters', 'organizations', 'locations', 'items']:
                if key in data:
                    data = data[key]
                    break

        canonical_uuids = set()
        for item in data:
            uuid = item.get('fabula_uuid')
            if uuid:
                canonical_uuids.add(uuid)

        self.stdout.write(f"\n{model_name}:")
        self.stdout.write(f"  Canonical in export: {len(canonical_uuids)}")

        # Find deprecated (in DB but not in export)
        all_objects = model_class.objects.all()
        self.stdout.write(f"  Total in database: {all_objects.count()}")

        deprecated = []
        for obj in all_objects:
            obj_uuid = getattr(obj, uuid_field, None)
            if obj_uuid and obj_uuid not in canonical_uuids:
                deprecated.append(obj)

        self.stdout.write(f"  Deprecated (to delete): {len(deprecated)}")

        if deprecated:
            for obj in deprecated[:5]:
                name = getattr(obj, 'canonical_name', None) or getattr(obj, 'title', str(obj))
                uuid = getattr(obj, uuid_field)
                self.stdout.write(f"    - {name} ({uuid})")
            if len(deprecated) > 5:
                self.stdout.write(f"    ... and {len(deprecated) - 5} more")

            if not dry_run:
                for obj in deprecated:
                    obj.delete()
                self.stdout.write(self.style.SUCCESS(f"  Deleted {len(deprecated)} {model_name} objects"))

        return len(deprecated)

    def cleanup_snippet(self, yaml_file, model_class, uuid_field, dry_run):
        """Cleanup a Django/Wagtail snippet model."""
        model_name = model_class.__name__

        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f) or []

        # Handle both list format and dict with key format
        if isinstance(data, dict):
            for key in ['locations', 'themes', 'arcs', 'items']:
                if key in data:
                    data = data[key]
                    break

        canonical_uuids = set()
        for item in data:
            uuid = item.get('fabula_uuid')
            if uuid:
                canonical_uuids.add(uuid)

        self.stdout.write(f"\n{model_name}:")
        self.stdout.write(f"  Canonical in export: {len(canonical_uuids)}")

        # Find deprecated
        all_objects = model_class.objects.all()
        self.stdout.write(f"  Total in database: {all_objects.count()}")

        deprecated = []
        for obj in all_objects:
            obj_uuid = getattr(obj, uuid_field, None)
            if obj_uuid and obj_uuid not in canonical_uuids:
                deprecated.append(obj)

        self.stdout.write(f"  Deprecated (to delete): {len(deprecated)}")

        if deprecated:
            for obj in deprecated[:5]:
                name = getattr(obj, 'canonical_name', None) or getattr(obj, 'name', str(obj))
                uuid = getattr(obj, uuid_field)
                self.stdout.write(f"    - {name} ({uuid})")
            if len(deprecated) > 5:
                self.stdout.write(f"    ... and {len(deprecated) - 5} more")

            if not dry_run:
                for obj in deprecated:
                    obj.delete()
                self.stdout.write(self.style.SUCCESS(f"  Deleted {len(deprecated)} {model_name} objects"))

        return len(deprecated)
