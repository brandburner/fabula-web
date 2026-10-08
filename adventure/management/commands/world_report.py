"""Project an episode and print what the graph supplies for a walkable world.

    python manage.py world_report --series wolf-hall --season 1 --episode 1
    python manage.py world_report --series wolf-hall --episode 1 --samples 3 --json
"""
import json

from django.core.management.base import BaseCommand, CommandError

from adventure import projection


class Command(BaseCommand):
    help = 'Coverage report for projecting one episode into an adventure world.'

    def add_arguments(self, parser):
        parser.add_argument('--series', required=True)
        parser.add_argument('--season', type=int, default=1)
        parser.add_argument('--episode', type=int, required=True)
        parser.add_argument('--samples', type=int, default=0, help='Print N sample event packets.')
        parser.add_argument('--json', action='store_true', help='Emit the report as JSON.')

    def handle(self, *args, **options):
        episode = projection.find_episode(options['series'], options['season'], options['episode'])
        if episode is None:
            raise CommandError('No live episode matches that series/season/episode.')
        world = projection.build_world(episode)
        rep = world['report']
        if options['json']:
            self.stdout.write(json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            self.stdout.write(f"{world['series']['title']} · {world['episode']['title']}")
            for key, value in rep.items():
                if isinstance(value, list):
                    self.stdout.write(f'{key}:')
                    for item in value:
                        self.stdout.write(f'    {item}')
                else:
                    self.stdout.write(f'{key}: {value}')
        for event in world['events'][:options['samples']]:
            self.stdout.write('\n=== ' + json.dumps(event, indent=1, ensure_ascii=False)[:3000])
