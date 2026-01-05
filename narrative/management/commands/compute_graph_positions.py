"""
Management command to compute 3D graph positions for characters.

Uses networkx spring_layout with co-occurrence edge weights.
Characters who frequently appear together in events cluster spatially.

Usage:
    python manage.py compute_graph_positions
    python manage.py compute_graph_positions --dry-run
    python manage.py compute_graph_positions --scale 100
    python manage.py compute_graph_positions --detect-communities
"""

import numpy as np
import networkx as nx
from collections import defaultdict

from django.core.management.base import BaseCommand

from narrative.models import CharacterPage, EventParticipation


class Command(BaseCommand):
    help = 'Compute 3D graph positions for characters based on co-occurrence in events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show positions without saving',
        )
        parser.add_argument(
            '--scale',
            type=float,
            default=50.0,
            help='Position scale range (default: 50, maps to [-50, 50])',
        )
        parser.add_argument(
            '--detect-communities',
            action='store_true',
            help='Run Louvain community detection',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show per-character positions',
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=100,
            help='Number of spring layout iterations (default: 100)',
        )

    def build_cooccurrence_graph(self):
        """Build weighted graph from character co-occurrences in events."""
        G = nx.Graph()

        self.stdout.write("  Building co-occurrence graph...")

        # Get all participations grouped by event
        event_characters = defaultdict(set)
        for p in EventParticipation.objects.values('event_id', 'character_id'):
            event_characters[p['event_id']].add(p['character_id'])

        self.stdout.write(f"  Found {len(event_characters)} events with participations")

        # Add all characters as nodes with tier attribute
        characters = CharacterPage.objects.all()
        char_tiers = {}
        for char in characters:
            G.add_node(char.pk, tier=char.importance_tier, title=char.title)
            char_tiers[char.pk] = char.importance_tier

        self.stdout.write(f"  Added {len(characters)} character nodes")

        # Build co-occurrence counts (how many events do pairs share?)
        cooccurrence_counts = defaultdict(int)
        for event_id, char_ids in event_characters.items():
            char_list = list(char_ids)
            # Create edges between all pairs of characters in this event
            for i, c1 in enumerate(char_list):
                for c2 in char_list[i + 1:]:
                    pair = tuple(sorted([c1, c2]))
                    cooccurrence_counts[pair] += 1

        # Add weighted edges
        for (c1, c2), weight in cooccurrence_counts.items():
            G.add_edge(c1, c2, weight=weight)

        self.stdout.write(f"  Added {len(cooccurrence_counts)} co-occurrence edges")

        # Log some statistics
        if cooccurrence_counts:
            weights = list(cooccurrence_counts.values())
            self.stdout.write(
                f"  Edge weights: min={min(weights)}, max={max(weights)}, "
                f"avg={sum(weights)/len(weights):.1f}"
            )

        return G, char_tiers

    def compute_positions(self, G, scale, iterations):
        """Compute 3D positions using spring layout."""
        self.stdout.write(f"  Computing spring layout (iterations={iterations})...")

        if len(G.nodes()) == 0:
            return {}

        # Spring layout with 3D positioning
        # weight='weight' makes characters with more shared events attract more strongly
        pos = nx.spring_layout(
            G,
            dim=3,
            weight='weight',
            k=None,  # Auto-compute optimal distance
            iterations=iterations,
            seed=42  # Reproducible results
        )

        if not pos:
            return {}

        # Convert to numpy array for normalization
        node_ids = list(pos.keys())
        coords = np.array([pos[node_id] for node_id in node_ids])

        # Normalize to [-scale, scale] range
        for i in range(3):
            col = coords[:, i]
            min_val, max_val = col.min(), col.max()
            range_val = max_val - min_val
            if range_val > 1e-10:
                coords[:, i] = 2 * scale * (col - min_val) / range_val - scale
            else:
                coords[:, i] = 0.0

        # Build result dictionary
        result = {}
        for idx, node_id in enumerate(node_ids):
            result[node_id] = {
                'x': float(coords[idx, 0]),
                'y': float(coords[idx, 1]),
                'z': float(coords[idx, 2]),
            }

        return result

    def detect_communities(self, G):
        """Detect communities using Louvain algorithm."""
        self.stdout.write("  Detecting communities (Louvain)...")

        if len(G.nodes()) == 0:
            return {}

        # Use Louvain community detection
        communities = nx.community.louvain_communities(G, seed=42)

        # Build node -> community mapping
        node_to_community = {}
        for comm_id, comm_nodes in enumerate(communities):
            for node in comm_nodes:
                node_to_community[node] = comm_id

        self.stdout.write(f"  Found {len(communities)} communities")

        return node_to_community

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        scale = options['scale']
        detect_communities = options['detect_communities']
        verbose = options['verbose']
        iterations = options['iterations']

        self.stdout.write(self.style.NOTICE(
            f"Computing 3D graph positions (scale={scale}, iterations={iterations})"
        ))

        # Build co-occurrence graph
        G, char_tiers = self.build_cooccurrence_graph()

        if len(G.nodes()) == 0:
            self.stdout.write(self.style.WARNING("No characters found."))
            return

        # Compute positions
        positions = self.compute_positions(G, scale, iterations)

        # Detect communities if requested
        communities = {}
        if detect_communities:
            communities = self.detect_communities(G)

        # Prepare updates
        characters_to_update = []
        characters = {c.pk: c for c in CharacterPage.objects.all()}

        tier_icons = {'anchor': '☀️', 'planet': '🪐', 'asteroid': '☄️'}

        for char_pk, pos in positions.items():
            if char_pk in characters:
                char = characters[char_pk]
                char.graph_x = pos['x']
                char.graph_y = pos['y']
                char.graph_z = pos['z']
                if detect_communities and char_pk in communities:
                    char.graph_community = communities[char_pk]
                characters_to_update.append(char)

                if verbose:
                    tier = char_tiers.get(char_pk, 'asteroid')
                    icon = tier_icons.get(tier, '?')
                    comm_str = f" [comm={communities.get(char_pk, 0)}]" if detect_communities else ""
                    self.stdout.write(
                        f"  {icon} {char.title}: "
                        f"({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f}){comm_str}"
                    )

        # Save or report
        if not dry_run:
            update_fields = ['graph_x', 'graph_y', 'graph_z']
            if detect_communities:
                update_fields.append('graph_community')

            CharacterPage.objects.bulk_update(characters_to_update, update_fields)
            self.stdout.write(self.style.SUCCESS(
                f"\nUpdated positions for {len(characters_to_update)} characters."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDry run - no changes saved. Would update {len(characters_to_update)} characters."
            ))

        # Summary statistics
        self.stdout.write(self.style.NOTICE("\n=== Summary ==="))
        self.stdout.write(f"  Characters positioned: {len(characters_to_update)}")
        self.stdout.write(f"  Co-occurrence edges: {G.number_of_edges()}")
        self.stdout.write(f"  Position range: [{-scale:.0f}, {scale:.0f}]")
        if detect_communities:
            unique_communities = len(set(communities.values()))
            self.stdout.write(f"  Communities detected: {unique_communities}")

        # Show tier distribution
        tier_counts = defaultdict(int)
        for char_pk in positions.keys():
            tier = char_tiers.get(char_pk, 'asteroid')
            tier_counts[tier] += 1

        self.stdout.write("\n  Tier distribution:")
        self.stdout.write(f"    ☀️  Anchors: {tier_counts.get('anchor', 0)}")
        self.stdout.write(f"    🪐 Planets: {tier_counts.get('planet', 0)}")
        self.stdout.write(f"    ☄️  Asteroids: {tier_counts.get('asteroid', 0)}")
