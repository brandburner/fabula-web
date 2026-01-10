"""
Management command to clean up duplicate character/entity and participation records.

Usage:
    python manage.py cleanup_duplicates --dry-run   # Preview what would be changed
    python manage.py cleanup_duplicates             # Actually merge and delete duplicates
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Min

from narrative.models import (
    CharacterPage,
    OrganizationPage,
    ObjectPage,
    Location,
    EventParticipation,
    ObjectInvolvement,
    LocationInvolvement,
    OrganizationInvolvement,
)


class Command(BaseCommand):
    help = 'Clean up duplicate character/entity and participation/involvement records'

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

        total_merged = 0
        total_deleted = 0

        # Phase 1: Merge duplicate entities (by canonical_name)
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Phase 1: Merging duplicate entities ===\n'))

        total_merged += self.merge_duplicate_characters(dry_run)
        total_merged += self.merge_duplicate_organizations(dry_run)
        total_merged += self.merge_duplicate_objects(dry_run)
        total_merged += self.merge_duplicate_locations(dry_run)

        # Phase 2: Clean up duplicate participation/involvement records
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Phase 2: Cleaning duplicate participations ===\n'))

        total_deleted += self.cleanup_duplicates(
            EventParticipation,
            'event_id', 'character_id',
            dry_run
        )

        total_deleted += self.cleanup_duplicates(
            ObjectInvolvement,
            'event_id', 'object_id',
            dry_run
        )

        total_deleted += self.cleanup_duplicates(
            LocationInvolvement,
            'event_id', 'location_id',
            dry_run
        )

        total_deleted += self.cleanup_duplicates(
            OrganizationInvolvement,
            'event_id', 'organization_id',
            dry_run
        )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nWould merge {total_merged} duplicate entities and delete {total_deleted} duplicate records'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nMerged {total_merged} duplicate entities and deleted {total_deleted} duplicate records'
            ))

    def merge_duplicate_characters(self, dry_run):
        """
        Merge duplicate CharacterPage records by canonical_name.
        Updates all EventParticipation records to point to the canonical character.
        """
        # Find duplicate canonical_names
        # Note: .order_by() clears Wagtail's default path ordering which breaks GROUP BY
        duplicates = CharacterPage.objects.values('canonical_name').annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1).order_by()

        dup_count = duplicates.count()
        if dup_count == 0:
            self.stdout.write('CharacterPage: No duplicate names found')
            return 0

        self.stdout.write(f'CharacterPage: Found {dup_count} names with duplicates')

        total_merged = 0
        for dup in duplicates:
            canonical_name = dup['canonical_name']
            min_id = dup['min_id']

            # Get the canonical character (lowest ID)
            canonical_char = CharacterPage.objects.get(id=min_id)

            # Get all duplicate characters (excluding the canonical one)
            duplicate_chars = CharacterPage.objects.filter(
                canonical_name=canonical_name
            ).exclude(id=min_id)

            for dup_char in duplicate_chars:
                # Count participations to migrate
                participations = EventParticipation.objects.filter(character=dup_char)
                part_count = participations.count()

                self.stdout.write(
                    f'  Merging "{canonical_name}" (pk={dup_char.pk}) -> (pk={canonical_char.pk}): '
                    f'{part_count} participations to migrate'
                )

                if not dry_run:
                    # Update participations to point to canonical character
                    # Use update to avoid duplicates - delete ones that would become duplicates
                    for part in participations:
                        existing = EventParticipation.objects.filter(
                            event=part.event,
                            character=canonical_char
                        ).first()

                        if existing:
                            # Already have a participation for this event+character, delete this one
                            part.delete()
                        else:
                            # Migrate to canonical character
                            part.character = canonical_char
                            part.save()

                    # Delete the duplicate character page
                    dup_char.delete()

                total_merged += 1

        if total_merged > 0:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'  Would merge {total_merged} duplicate CharacterPage records'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'  Merged {total_merged} duplicate CharacterPage records'
                ))

        return total_merged

    def merge_duplicate_organizations(self, dry_run):
        """Merge duplicate OrganizationPage records by canonical_name."""
        # Note: .order_by() clears Wagtail's default path ordering which breaks GROUP BY
        duplicates = OrganizationPage.objects.values('canonical_name').annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1).order_by()

        dup_count = duplicates.count()
        if dup_count == 0:
            self.stdout.write('OrganizationPage: No duplicate names found')
            return 0

        self.stdout.write(f'OrganizationPage: Found {dup_count} names with duplicates')

        total_merged = 0
        for dup in duplicates:
            canonical_name = dup['canonical_name']
            min_id = dup['min_id']

            canonical_org = OrganizationPage.objects.get(id=min_id)
            duplicate_orgs = OrganizationPage.objects.filter(
                canonical_name=canonical_name
            ).exclude(id=min_id)

            for dup_org in duplicate_orgs:
                involvements = OrganizationInvolvement.objects.filter(organization=dup_org)
                inv_count = involvements.count()

                self.stdout.write(
                    f'  Merging "{canonical_name}" (pk={dup_org.pk}) -> (pk={canonical_org.pk}): '
                    f'{inv_count} involvements to migrate'
                )

                if not dry_run:
                    for inv in involvements:
                        existing = OrganizationInvolvement.objects.filter(
                            event=inv.event,
                            organization=canonical_org
                        ).first()

                        if existing:
                            inv.delete()
                        else:
                            inv.organization = canonical_org
                            inv.save()

                    # Update character affiliations
                    CharacterPage.objects.filter(affiliated_organization=dup_org).update(
                        affiliated_organization=canonical_org
                    )

                    dup_org.delete()

                total_merged += 1

        if total_merged > 0:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'  Would merge {total_merged} duplicate OrganizationPage records'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'  Merged {total_merged} duplicate OrganizationPage records'
                ))

        return total_merged

    def merge_duplicate_objects(self, dry_run):
        """Merge duplicate ObjectPage records by canonical_name."""
        # Note: .order_by() clears Wagtail's default path ordering which breaks GROUP BY
        duplicates = ObjectPage.objects.values('canonical_name').annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1).order_by()

        dup_count = duplicates.count()
        if dup_count == 0:
            self.stdout.write('ObjectPage: No duplicate names found')
            return 0

        self.stdout.write(f'ObjectPage: Found {dup_count} names with duplicates')

        total_merged = 0
        for dup in duplicates:
            canonical_name = dup['canonical_name']
            min_id = dup['min_id']

            canonical_obj = ObjectPage.objects.get(id=min_id)
            duplicate_objs = ObjectPage.objects.filter(
                canonical_name=canonical_name
            ).exclude(id=min_id)

            for dup_obj in duplicate_objs:
                involvements = ObjectInvolvement.objects.filter(object=dup_obj)
                inv_count = involvements.count()

                self.stdout.write(
                    f'  Merging "{canonical_name}" (pk={dup_obj.pk}) -> (pk={canonical_obj.pk}): '
                    f'{inv_count} involvements to migrate'
                )

                if not dry_run:
                    for inv in involvements:
                        existing = ObjectInvolvement.objects.filter(
                            event=inv.event,
                            object=canonical_obj
                        ).first()

                        if existing:
                            inv.delete()
                        else:
                            inv.object = canonical_obj
                            inv.save()

                    dup_obj.delete()

                total_merged += 1

        if total_merged > 0:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'  Would merge {total_merged} duplicate ObjectPage records'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'  Merged {total_merged} duplicate ObjectPage records'
                ))

        return total_merged

    def merge_duplicate_locations(self, dry_run):
        """Merge duplicate Location records by canonical_name."""
        duplicates = Location.objects.values('canonical_name').annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1)

        dup_count = duplicates.count()
        if dup_count == 0:
            self.stdout.write('Location: No duplicate names found')
            return 0

        self.stdout.write(f'Location: Found {dup_count} names with duplicates')

        total_merged = 0
        for dup in duplicates:
            canonical_name = dup['canonical_name']
            min_id = dup['min_id']

            canonical_loc = Location.objects.get(id=min_id)
            duplicate_locs = Location.objects.filter(
                canonical_name=canonical_name
            ).exclude(id=min_id)

            for dup_loc in duplicate_locs:
                involvements = LocationInvolvement.objects.filter(location=dup_loc)
                inv_count = involvements.count()

                self.stdout.write(
                    f'  Merging "{canonical_name}" (pk={dup_loc.pk}) -> (pk={canonical_loc.pk}): '
                    f'{inv_count} involvements to migrate'
                )

                if not dry_run:
                    for inv in involvements:
                        existing = LocationInvolvement.objects.filter(
                            event=inv.event,
                            location=canonical_loc
                        ).first()

                        if existing:
                            inv.delete()
                        else:
                            inv.location = canonical_loc
                            inv.save()

                    # Update event primary locations
                    from narrative.models import EventPage
                    EventPage.objects.filter(location=dup_loc).update(location=canonical_loc)

                    dup_loc.delete()

                total_merged += 1

        if total_merged > 0:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'  Would merge {total_merged} duplicate Location records'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'  Merged {total_merged} duplicate Location records'
                ))

        return total_merged

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
