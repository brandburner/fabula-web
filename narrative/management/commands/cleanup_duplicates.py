"""
Management command to clean up duplicate participation and involvement records.

Usage:
    python manage.py cleanup_duplicates --dry-run   # Preview what would be deleted
    python manage.py cleanup_duplicates             # Actually delete duplicates
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Min

from narrative.models import (
    EventParticipation,
    ObjectInvolvement,
    LocationInvolvement,
    OrganizationInvolvement,
)


class Command(BaseCommand):
    help = 'Clean up duplicate participation and involvement records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview duplicates without deleting'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made\n'))

        total_deleted = 0

        # Clean up EventParticipation duplicates
        total_deleted += self.cleanup_duplicates(
            EventParticipation,
            'event_id', 'character_id',
            dry_run
        )

        # Clean up ObjectInvolvement duplicates
        total_deleted += self.cleanup_duplicates(
            ObjectInvolvement,
            'event_id', 'object_id',
            dry_run
        )

        # Clean up LocationInvolvement duplicates
        total_deleted += self.cleanup_duplicates(
            LocationInvolvement,
            'event_id', 'location_id',
            dry_run
        )

        # Clean up OrganizationInvolvement duplicates
        total_deleted += self.cleanup_duplicates(
            OrganizationInvolvement,
            'event_id', 'organization_id',
            dry_run
        )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nWould delete {total_deleted} duplicate records total'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nDeleted {total_deleted} duplicate records total'
            ))

    def cleanup_duplicates(self, model, field1, field2, dry_run):
        """
        Find and remove duplicate records for a model.

        Keeps the record with the lowest ID (oldest) and removes newer duplicates.
        """
        model_name = model.__name__

        # Find groups with duplicates
        duplicates = model.objects.values(field1, field2).annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1)

        dup_count = duplicates.count()

        if dup_count == 0:
            self.stdout.write(f'{model_name}: No duplicates found')
            return 0

        self.stdout.write(f'{model_name}: Found {dup_count} groups with duplicates')

        total_to_delete = 0
        ids_to_delete = []

        for dup in duplicates:
            # Get all records in this group except the one with min_id
            records = model.objects.filter(
                **{field1: dup[field1], field2: dup[field2]}
            ).exclude(id=dup['min_id'])

            count = records.count()
            total_to_delete += count
            ids_to_delete.extend(records.values_list('id', flat=True))

            if count > 0:
                self.stdout.write(
                    f'  {field1}={dup[field1]}, {field2}={dup[field2]}: '
                    f'{count} extra records'
                )

        if not dry_run and ids_to_delete:
            model.objects.filter(id__in=ids_to_delete).delete()
            self.stdout.write(self.style.SUCCESS(
                f'  Deleted {total_to_delete} duplicate {model_name} records'
            ))
        elif dry_run and ids_to_delete:
            self.stdout.write(self.style.WARNING(
                f'  Would delete {total_to_delete} duplicate {model_name} records'
            ))

        return total_to_delete
