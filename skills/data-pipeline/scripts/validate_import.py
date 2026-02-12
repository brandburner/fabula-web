"""
Post-import validation script for Fabula data pipeline.

Run in Django shell after every import:
    DJANGO_SETTINGS_MODULE=fabula_web.settings.dev python manage.py shell < skills/data-pipeline/scripts/validate_import.py

Or paste into an interactive shell session.
"""

from django.db.models import Count, Q
from narrative.models import (
    CharacterPage, OrganizationPage, ObjectPage, EventPage,
    SeriesIndexPage, SeasonPage, EpisodePage,
    Theme, ConflictArc, Location, Writer,
    EventParticipation, NarrativeConnection,
    ObjectInvolvement, LocationInvolvement, OrganizationInvolvement,
    WritingCredit, Act, PlotBeat, EventBeatLink,
)

print("=" * 60)
print("FABULA IMPORT VALIDATION")
print("=" * 60)

# --- Entity Counts ---
print("\n--- Page Counts ---")
for Model in [SeriesIndexPage, SeasonPage, EpisodePage, CharacterPage,
              OrganizationPage, ObjectPage, EventPage]:
    count = Model.objects.live().count()
    print(f"  {Model.__name__:<25} {count:>6}")

print("\n--- Snippet Counts ---")
for Model in [Theme, ConflictArc, Location, Writer]:
    count = Model.objects.count()
    print(f"  {Model.__name__:<25} {count:>6}")

print("\n--- Relationship Counts ---")
for Model in [EventParticipation, NarrativeConnection, ObjectInvolvement,
              LocationInvolvement, OrganizationInvolvement, WritingCredit]:
    count = Model.objects.count()
    print(f"  {Model.__name__:<25} {count:>6}")

print("\n--- Structure Counts ---")
for Model in [Act, PlotBeat, EventBeatLink]:
    count = Model.objects.count()
    print(f"  {Model.__name__:<25} {count:>6}")

# --- Duplicate Detection ---
print("\n--- Duplicate Check ---")
warnings = 0

chars = CharacterPage.objects.live()
char_dupes = chars.values('canonical_name').annotate(cnt=Count('id')).filter(cnt__gt=1)
if char_dupes.exists():
    warnings += 1
    print(f"  WARNING: {char_dupes.count()} duplicate character names:")
    for d in char_dupes[:5]:
        print(f"    {d['canonical_name']}: {d['cnt']}x")
else:
    print("  Characters: No duplicates")

orgs = OrganizationPage.objects.live()
org_dupes = orgs.values('canonical_name').annotate(cnt=Count('id')).filter(cnt__gt=1)
if org_dupes.exists():
    warnings += 1
    print(f"  WARNING: {org_dupes.count()} duplicate organization names:")
    for d in org_dupes[:5]:
        print(f"    {d['canonical_name']}: {d['cnt']}x")
else:
    print("  Organizations: No duplicates")

# --- Trait Coverage ---
print("\n--- Trait Coverage ---")
total_chars = chars.count()
with_traits = chars.exclude(traits=[]).count()
pct = (100 * with_traits // total_chars) if total_chars else 0
status = "OK" if pct >= 80 else "WARNING"
print(f"  {status}: {with_traits}/{total_chars} characters have traits ({pct}%)")
if pct < 80:
    warnings += 1

# --- Orphan Detection ---
print("\n--- Orphan Detection ---")
events_without_episode = EventPage.objects.live().filter(episode__isnull=True).count()
if events_without_episode:
    warnings += 1
    print(f"  WARNING: {events_without_episode} events without episode FK")
else:
    print("  Events: All linked to episodes")

participations_broken = EventParticipation.objects.filter(
    Q(event__isnull=True) | Q(character__isnull=True)
).count()
if participations_broken:
    warnings += 1
    print(f"  WARNING: {participations_broken} participations with broken FKs")
else:
    print("  Participations: All FKs intact")

connections_broken = NarrativeConnection.objects.filter(
    Q(from_event__isnull=True) | Q(to_event__isnull=True)
).count()
if connections_broken:
    warnings += 1
    print(f"  WARNING: {connections_broken} connections with broken FKs")
else:
    print("  Connections: All FKs intact")

# --- Per-Series Breakdown ---
print("\n--- Per-Series Breakdown ---")
for series in SeriesIndexPage.objects.all():
    events = EventPage.objects.live().descendant_of(series).count()
    seasons = SeasonPage.objects.live().child_of(series).count()
    episodes = EpisodePage.objects.live().descendant_of(series).count()
    print(f"  {series.title}: {seasons} seasons, {episodes} episodes, {events} events")

# --- Summary ---
print("\n" + "=" * 60)
if warnings == 0:
    print("RESULT: ALL CHECKS PASSED")
else:
    print(f"RESULT: {warnings} WARNING(S) - review above")
print("=" * 60)
