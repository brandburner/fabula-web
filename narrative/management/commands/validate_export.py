"""
Django management command to validate Fabula YAML export files.

This command performs comprehensive validation of exported YAML data:
1. Entity linkage integrity (all references point to existing entities)
2. Participation data richness (emotional_state, goals, etc.)
3. Connection data completeness (descriptions, valid types)

Usage:
    python manage.py validate_export --input ./fabula_export
    python manage.py validate_export --input ./fabula_export --verbose
    python manage.py validate_export --input ./fabula_export --strict
"""

import yaml
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Validate Fabula YAML export files for integrity and completeness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input', '-i',
            type=str,
            default='./fabula_export',
            help='Input directory containing YAML export files (default: ./fabula_export)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed error messages'
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Fail on any validation error'
        )
        parser.add_argument(
            '--check-richness',
            action='store_true',
            default=True,
            help='Check participation data richness (default: True)'
        )

    def handle(self, *args, **options):
        input_dir = Path(options['input']).absolute()
        verbose = options['verbose']
        strict = options['strict']
        check_richness = options['check_richness']

        if not input_dir.exists():
            raise CommandError(f"Input directory not found: {input_dir}")

        self.stdout.write(self.style.SUCCESS(f"\nValidating export: {input_dir}\n"))
        self.stdout.write("=" * 60)

        validator = ExportValidator(input_dir, verbose=verbose)

        # Run validation
        validator.load_all_data()
        results = validator.validate_all()

        # Print results
        self.print_results(results)

        # Participation richness analysis
        if check_richness:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("\nParticipation Richness Analysis"))
            self.stdout.write("-" * 40)
            richness = validator.analyze_richness()
            self.print_richness(richness)

        # Summary
        self.stdout.write("\n" + "=" * 60)
        total_errors = sum(r['errors'] for r in results.values())
        total_warnings = sum(r['warnings'] for r in results.values())

        if total_errors == 0:
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Validation PASSED ({total_warnings} warnings)"
            ))
        else:
            msg = f"\n✗ Validation FAILED: {total_errors} errors, {total_warnings} warnings"
            if strict:
                raise CommandError(msg)
            else:
                self.stdout.write(self.style.ERROR(msg))

    def print_results(self, results: Dict):
        """Print validation results."""
        for check_name, result in results.items():
            if result['errors'] == 0:
                status = self.style.SUCCESS(f"✓ {check_name}")
            else:
                status = self.style.ERROR(f"✗ {check_name}: {result['errors']} errors")

            self.stdout.write(status)

            if result.get('details'):
                for detail in result['details'][:5]:  # Show first 5
                    self.stdout.write(f"  • {detail}")
                if len(result['details']) > 5:
                    self.stdout.write(f"  ... and {len(result['details']) - 5} more")

    def print_richness(self, richness: Dict):
        """Print participation richness analysis."""
        self.stdout.write(f"\nTotal Participations: {richness['total']}")

        rich_pct = richness['rich_percentage']
        if rich_pct >= 80:
            style = self.style.SUCCESS
        elif rich_pct >= 50:
            style = self.style.WARNING
        else:
            style = self.style.ERROR

        self.stdout.write(style(
            f"Rich Participations: {richness['rich']} ({rich_pct:.1f}%)"
        ))

        self.stdout.write("\nField Coverage:")
        for field, data in richness['field_coverage'].items():
            pct = data['percentage']
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            self.stdout.write(f"  {field:20s} {bar} {pct:5.1f}%")


class ExportValidator:
    """Validates Fabula export data."""

    def __init__(self, export_dir: Path, verbose: bool = False):
        self.export_dir = export_dir
        self.verbose = verbose

        # Data stores
        self.characters: List[Dict] = []
        self.locations: List[Dict] = []
        self.organizations: List[Dict] = []
        self.themes: List[Dict] = []
        self.arcs: List[Dict] = []
        self.connections: List[Dict] = []
        self.events: List[Dict] = []

        # UUID lookup sets
        self.character_uuids: Set[str] = set()
        self.location_uuids: Set[str] = set()
        self.organization_uuids: Set[str] = set()
        self.theme_uuids: Set[str] = set()
        self.arc_uuids: Set[str] = set()
        self.event_uuids: Set[str] = set()

    def load_yaml(self, filename: str) -> Optional[Any]:
        """Load a YAML file."""
        filepath = self.export_dir / filename
        if not filepath.exists():
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def extract_list(self, data: Any, keys: List[str] = None) -> List[Dict]:
        """Extract a list from various YAML structures."""
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in (keys or ['items', 'data']):
                if key in data:
                    return data[key]
            return [data]
        return []

    def load_all_data(self):
        """Load all YAML data files."""
        # Characters
        data = self.load_yaml('characters.yaml')
        self.characters = self.extract_list(data, ['characters'])
        self.character_uuids = {c.get('fabula_uuid') for c in self.characters if c.get('fabula_uuid')}

        # Locations
        data = self.load_yaml('locations.yaml')
        self.locations = self.extract_list(data, ['locations'])
        self.location_uuids = {l.get('fabula_uuid') for l in self.locations if l.get('fabula_uuid')}

        # Organizations
        data = self.load_yaml('organizations.yaml')
        self.organizations = self.extract_list(data, ['organizations'])
        self.organization_uuids = {o.get('fabula_uuid') for o in self.organizations if o.get('fabula_uuid')}

        # Themes
        data = self.load_yaml('themes.yaml')
        self.themes = self.extract_list(data, ['themes'])
        self.theme_uuids = {t.get('fabula_uuid') for t in self.themes if t.get('fabula_uuid')}

        # Arcs
        data = self.load_yaml('arcs.yaml')
        self.arcs = self.extract_list(data, ['arcs'])
        self.arc_uuids = {a.get('fabula_uuid') for a in self.arcs if a.get('fabula_uuid')}

        # Connections
        data = self.load_yaml('connections.yaml')
        self.connections = self.extract_list(data, ['connections'])

        # Events (from all episode files)
        events_dir = self.export_dir / 'events'
        if events_dir.exists():
            for yaml_file in sorted(events_dir.glob('*.yaml')):
                data = self.load_yaml(f'events/{yaml_file.name}')
                if data and 'events' in data:
                    self.events.extend(data['events'])

        self.event_uuids = {e.get('fabula_uuid') for e in self.events if e.get('fabula_uuid')}

    def validate_all(self) -> Dict[str, Dict]:
        """Run all validation checks."""
        return {
            'Characters': self.validate_characters(),
            'Locations': self.validate_locations(),
            'Themes': self.validate_themes(),
            'Arcs': self.validate_arcs(),
            'Events': self.validate_events(),
            'Participations': self.validate_participations(),
            'Connections': self.validate_connections(),
        }

    def validate_characters(self) -> Dict:
        """Validate character data."""
        errors = 0
        details = []

        for char in self.characters:
            uuid = char.get('fabula_uuid')
            if not uuid:
                errors += 1
                details.append("Character missing fabula_uuid")
            if not char.get('canonical_name'):
                errors += 1
                details.append(f"Character {uuid} missing canonical_name")

        return {'errors': errors, 'warnings': 0, 'details': details}

    def validate_locations(self) -> Dict:
        """Validate location data."""
        errors = 0
        details = []

        for loc in self.locations:
            uuid = loc.get('fabula_uuid')
            if not uuid:
                errors += 1
                details.append("Location missing fabula_uuid")
            if not loc.get('canonical_name'):
                errors += 1
                details.append(f"Location {uuid} missing canonical_name")

        return {'errors': errors, 'warnings': 0, 'details': details}

    def validate_themes(self) -> Dict:
        """Validate theme data."""
        errors = 0
        details = []

        for theme in self.themes:
            uuid = theme.get('fabula_uuid')
            if not uuid:
                errors += 1
                details.append("Theme missing fabula_uuid")
            if not theme.get('name'):
                errors += 1
                details.append(f"Theme {uuid} missing name")

        return {'errors': errors, 'warnings': 0, 'details': details}

    def validate_arcs(self) -> Dict:
        """Validate conflict arc data."""
        errors = 0
        warnings = 0
        details = []

        valid_types = ['INTERNAL', 'INTERPERSONAL', 'SOCIETAL', 'ENVIRONMENTAL', 'TECHNOLOGICAL']

        for arc in self.arcs:
            uuid = arc.get('fabula_uuid')
            if not uuid:
                errors += 1
                details.append("Arc missing fabula_uuid")
            if not arc.get('title') and not arc.get('description'):
                errors += 1
                details.append(f"Arc {uuid} missing title/description")

            arc_type = arc.get('arc_type')
            if arc_type and arc_type not in valid_types:
                warnings += 1
                details.append(f"Arc {uuid} has unknown type: {arc_type}")

        return {'errors': errors, 'warnings': warnings, 'details': details}

    def validate_events(self) -> Dict:
        """Validate event data."""
        errors = 0
        warnings = 0
        details = []

        for event in self.events:
            uuid = event.get('fabula_uuid')
            if not uuid:
                errors += 1
                details.append("Event missing fabula_uuid")
                continue

            if not event.get('title'):
                warnings += 1
                details.append(f"Event {uuid} missing title")

            if not event.get('description'):
                warnings += 1
                details.append(f"Event {uuid} missing description")

            # Validate location reference
            loc_uuid = event.get('location_uuid')
            if loc_uuid and loc_uuid not in self.location_uuids:
                errors += 1
                details.append(f"Event {uuid} references unknown location: {loc_uuid}")

            # Validate theme references
            for theme_uuid in event.get('theme_uuids', []):
                if theme_uuid not in self.theme_uuids:
                    errors += 1
                    details.append(f"Event {uuid} references unknown theme: {theme_uuid}")

            # Validate arc references
            for arc_uuid in event.get('arc_uuids', []):
                if arc_uuid not in self.arc_uuids:
                    errors += 1
                    details.append(f"Event {uuid} references unknown arc: {arc_uuid}")

        return {'errors': errors, 'warnings': warnings, 'details': details}

    def validate_participations(self) -> Dict:
        """Validate participation data and linkages."""
        errors = 0
        warnings = 0
        details = []

        for event in self.events:
            event_uuid = event.get('fabula_uuid', 'unknown')

            for p in event.get('participations', []):
                char_uuid = p.get('character_uuid')

                if not char_uuid:
                    errors += 1
                    details.append(f"Event {event_uuid}: participation missing character_uuid")
                    continue

                if char_uuid not in self.character_uuids:
                    errors += 1
                    details.append(f"Event {event_uuid}: unknown character {char_uuid}")

        return {'errors': errors, 'warnings': warnings, 'details': details}

    def validate_connections(self) -> Dict:
        """Validate narrative connection data."""
        errors = 0
        warnings = 0
        details = []

        valid_types = [
            'CAUSAL', 'FORESHADOWING', 'THEMATIC_PARALLEL',
            'CHARACTER_CONTINUITY', 'ESCALATION', 'CALLBACK',
            'EMOTIONAL_ECHO', 'SYMBOLIC_PARALLEL', 'TEMPORAL',
            'NARRATIVELY_FOLLOWS'
        ]

        valid_strengths = ['strong', 'medium', 'weak']

        for conn in self.connections:
            uuid = conn.get('fabula_uuid', 'unknown')

            # Validate event references
            from_uuid = conn.get('from_event_uuid')
            to_uuid = conn.get('to_event_uuid')

            if not from_uuid:
                errors += 1
                details.append(f"Connection {uuid} missing from_event_uuid")
            elif from_uuid not in self.event_uuids:
                errors += 1
                details.append(f"Connection {uuid} from unknown event: {from_uuid}")

            if not to_uuid:
                errors += 1
                details.append(f"Connection {uuid} missing to_event_uuid")
            elif to_uuid not in self.event_uuids:
                errors += 1
                details.append(f"Connection {uuid} to unknown event: {to_uuid}")

            # Validate connection type
            conn_type = conn.get('connection_type')
            if not conn_type:
                errors += 1
                details.append(f"Connection {uuid} missing connection_type")
            elif conn_type not in valid_types:
                warnings += 1
                details.append(f"Connection {uuid} has unknown type: {conn_type}")

            # Validate strength
            strength = conn.get('strength')
            if strength and strength not in valid_strengths:
                warnings += 1
                details.append(f"Connection {uuid} has unknown strength: {strength}")

            # Check for description (the narrative assertion)
            if not conn.get('description'):
                warnings += 1
                details.append(f"Connection {uuid} missing description")

        return {'errors': errors, 'warnings': warnings, 'details': details}

    def analyze_richness(self) -> Dict:
        """Analyze participation data richness."""
        total = 0
        rich = 0
        field_counts = defaultdict(int)

        for event in self.events:
            for p in event.get('participations', []):
                total += 1

                # Check each field
                if p.get('emotional_state'):
                    field_counts['emotional_state'] += 1
                if p.get('goals') and len(p['goals']) > 0:
                    field_counts['goals'] += 1
                if p.get('what_happened'):
                    field_counts['what_happened'] += 1
                if p.get('observed_status'):
                    field_counts['observed_status'] += 1
                if p.get('beliefs') and len(p['beliefs']) > 0:
                    field_counts['beliefs'] += 1
                if p.get('observed_traits') and len(p['observed_traits']) > 0:
                    field_counts['observed_traits'] += 1

                # Rich = has emotional_state OR goals
                if p.get('emotional_state') or (p.get('goals') and len(p['goals']) > 0):
                    rich += 1

        field_coverage = {}
        for field in ['emotional_state', 'goals', 'what_happened', 'observed_status', 'beliefs', 'observed_traits']:
            count = field_counts[field]
            percentage = (count / total * 100) if total > 0 else 0
            field_coverage[field] = {'count': count, 'percentage': percentage}

        return {
            'total': total,
            'rich': rich,
            'sparse': total - rich,
            'rich_percentage': (rich / total * 100) if total > 0 else 0,
            'field_coverage': field_coverage
        }
