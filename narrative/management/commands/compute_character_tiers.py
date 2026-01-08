"""
Management command to compute character importance tiers.

This command calculates the Graph Gravity-inspired importance tier for each character
based on their episode appearances and relationship density (co-participants).

Usage:
    python manage.py compute_character_tiers
    python manage.py compute_character_tiers --dry-run
    python manage.py compute_character_tiers --verbose
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Count, Q

from narrative.models import CharacterPage, EventParticipation, ImportanceTier


class Command(BaseCommand):
    help = 'Compute importance tiers for all characters based on episode appearances and relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show per-character tier assignments',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']

        # Get thresholds from settings
        anchor_min_episodes = getattr(settings, 'TIER_ANCHOR_MIN_EPISODES', 5)
        anchor_min_relationships = getattr(settings, 'TIER_ANCHOR_MIN_RELATIONSHIPS', 20)
        planet_min_episodes = getattr(settings, 'TIER_PLANET_MIN_EPISODES', 2)
        planet_min_relationships = getattr(settings, 'TIER_PLANET_MIN_RELATIONSHIPS', 5)

        self.stdout.write(self.style.NOTICE(
            f"Tier thresholds: "
            f"Anchor (episodes>={anchor_min_episodes} OR relationships>={anchor_min_relationships}), "
            f"Planet (episodes>={planet_min_episodes} OR relationships>={planet_min_relationships})"
        ))

        characters = CharacterPage.objects.all()
        total = characters.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No characters found."))
            return

        self.stdout.write(f"Processing {total} characters...")

        # Track statistics
        stats = {
            'anchor': 0,
            'planet': 0,
            'asteroid': 0,
            'promoted': 0,
            'demoted': 0,
            'unchanged': 0,
        }

        characters_to_update = []

        for i, character in enumerate(characters, 1):
            # 1. Count total event participations (appearance_count)
            appearance_count = EventParticipation.objects.filter(
                character=character
            ).count()

            # 2. Count distinct episodes via participations
            episode_count = EventParticipation.objects.filter(
                character=character
            ).values('event__episode').distinct().count()

            # 3. Count unique co-participants (other characters in same events)
            # Get all events this character participated in
            character_events = EventParticipation.objects.filter(
                character=character
            ).values_list('event_id', flat=True)

            # Count unique other characters who participated in those events
            relationship_count = EventParticipation.objects.filter(
                event_id__in=character_events
            ).exclude(
                character=character
            ).values('character').distinct().count()

            # 4. Determine tier based on thresholds
            if (episode_count >= anchor_min_episodes or
                    relationship_count >= anchor_min_relationships):
                new_tier = ImportanceTier.ANCHOR
            elif (episode_count >= planet_min_episodes or
                  relationship_count >= planet_min_relationships):
                new_tier = ImportanceTier.PLANET
            else:
                new_tier = ImportanceTier.ASTEROID

            # Track changes
            old_tier = character.importance_tier
            if old_tier != new_tier:
                tier_order = {'asteroid': 0, 'planet': 1, 'anchor': 2}
                if tier_order.get(new_tier, 0) > tier_order.get(old_tier, 0):
                    stats['promoted'] += 1
                else:
                    stats['demoted'] += 1
            else:
                stats['unchanged'] += 1

            stats[new_tier] += 1

            # Update character object
            character.appearance_count = appearance_count
            character.episode_count = episode_count
            character.relationship_count = relationship_count
            character.importance_tier = new_tier
            characters_to_update.append(character)

            # Verbose output
            if verbose:
                tier_icon = {'anchor': '☀️', 'planet': '🪐', 'asteroid': '☄️'}.get(new_tier, '?')
                change_indicator = ''
                if old_tier != new_tier:
                    old_icon = {'anchor': '☀️', 'planet': '🪐', 'asteroid': '☄️'}.get(old_tier, '?')
                    change_indicator = f" ({old_icon} → {tier_icon})"
                self.stdout.write(
                    f"  {tier_icon} {character.title}: "
                    f"episodes={episode_count}, relationships={relationship_count}{change_indicator}"
                )

            # Progress indicator (every 100 characters)
            if i % 100 == 0 and not verbose:
                self.stdout.write(f"  Processed {i}/{total}...")

        # Save changes (unless dry-run)
        if not dry_run:
            CharacterPage.objects.bulk_update(
                characters_to_update,
                ['appearance_count', 'episode_count', 'relationship_count', 'importance_tier']
            )
            self.stdout.write(self.style.SUCCESS(f"\nUpdated {len(characters_to_update)} characters."))
        else:
            self.stdout.write(self.style.WARNING(f"\nDry run - no changes saved."))

        # Print summary
        self.stdout.write(self.style.NOTICE("\n=== Summary ==="))
        self.stdout.write(f"  ☀️  Anchors: {stats['anchor']}")
        self.stdout.write(f"  🪐 Planets: {stats['planet']}")
        self.stdout.write(f"  ☄️  Asteroids: {stats['asteroid']}")
        self.stdout.write(f"  ⬆️  Promoted: {stats['promoted']}")
        self.stdout.write(f"  ⬇️  Demoted: {stats['demoted']}")
        self.stdout.write(f"  ➡️  Unchanged: {stats['unchanged']}")
