"""Inspect and retire shared passages in a projected world.

Retiring keeps the row as history and stops it serving anyone; the next
visitor to ask writes a fresh passage. Nothing changes without --apply.

    # what the world holds (add --grep to filter by key or text, --retired for history)
    python manage.py retire_passage wolf-hall-e1 --list --grep esher

    # retire one passage by key (both backends unless --backend) or by row id
    python manage.py retire_passage wolf-hall-e1 look:cand_evt_scene_... --reason "invents a door" --apply
    python manage.py retire_passage wolf-hall-e1 --id 42 --apply

    # sweep live LLM passages through the grounding check; --apply retires failures
    python manage.py retire_passage wolf-hall-e1 --check

    # after a re-import or a change to what the narrator is sent: carry LLM
    # passages forward to the new record where they still pass, retire the rest
    python manage.py retire_passage wolf-hall-e1 --carry-forward --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.http import Http404

from adventure import narrator, scenarios, store
from adventure.models import WorldPassage


class Command(BaseCommand):
    help = 'List, check and retire shared passages in a projected adventure world.'

    def add_arguments(self, parser):
        parser.add_argument('world', help='World slug from ADVENTURE_WORLDS, e.g. wolf-hall-e1')
        parser.add_argument('key', nargs='?', help='Passage key to retire, e.g. look:<event uuid>')
        parser.add_argument('--id', type=int, action='append', default=[], help='Row id to retire (repeatable).')
        parser.add_argument('--backend', choices=['local', 'openrouter'], help='Only this backend.')
        parser.add_argument('--reason', default='retired by an editor', help='Why, kept on the row.')
        parser.add_argument('--list', action='store_true', help='List passages instead of retiring.')
        parser.add_argument('--grep', help='With --list: only keys or text containing this.')
        parser.add_argument('--retired', action='store_true', help='With --list: include retired rows.')
        parser.add_argument('--check', action='store_true', help='Run the grounding check over live LLM passages.')
        parser.add_argument('--carry-forward', action='store_true',
                            help='Re-check stale LLM passages against the current record; adopt or retire them.')
        parser.add_argument('--apply', action='store_true', help='Actually retire. Without it, only report.')

    def handle(self, *args, **opts):
        slug = opts['world']
        try:
            scenario = scenarios.get(slug)
            if not hasattr(scenario, 'config'):
                raise CommandError(f'{slug} is the authored prototype; it has no shared passages.')
            world = scenario.world
        except Http404:
            raise CommandError(f'{slug} is not a projected world in ADVENTURE_WORLDS, or its episode is not live.')
        hashes = store.current_hashes(world)
        if opts['list']:
            return self.list_passages(slug, hashes, opts)
        if opts['check']:
            return self.check_grounding(slug, world, hashes, opts)
        if opts['carry_forward']:
            return self.carry_forward(slug, world, hashes, opts)
        if not opts['key'] and not opts['id']:
            raise CommandError('Give a passage key, --id, --list or --check.')
        rows = store.live(slug)
        rows = rows.filter(pk__in=opts['id']) if opts['id'] else rows.filter(key=opts['key'])
        if opts['backend']:
            rows = rows.filter(backend=opts['backend'])
        rows = list(rows.order_by('id'))
        if not rows:
            raise CommandError('No live passage matches.')
        for row in rows:
            self.stdout.write(self.describe(row, hashes))
            if row.backend == 'local' and hashes.get(row.key) == row.packet_hash:
                self.stdout.write('    note: local passages are the record verbatim; a rewrite will be identical '
                                  'unless the record changes.')
        if not opts['apply']:
            self.stdout.write(f'Dry run: {len(rows)} passage(s) would be retired. Add --apply.')
            return
        count = store.retire(WorldPassage.objects.filter(pk__in=[r.pk for r in rows]), opts['reason'])
        self.stdout.write(self.style.SUCCESS(f'Retired {count} passage(s). The next request writes a fresh one.'))

    def describe(self, row, hashes):
        state = 'retired · ' + row.retired_reason if row.retired_at else (
            'live' if hashes.get(row.key) == row.packet_hash else 'stale: the record has changed')
        text = row.text.replace('\n', ' ')
        return f'#{row.pk} [{row.backend}] {row.key}  ({state})\n    {text[:160]}{"…" if len(text) > 160 else ""}'

    def list_passages(self, slug, hashes, opts):
        rows = WorldPassage.objects.filter(world=slug)
        if not opts['retired']:
            rows = rows.filter(retired_at__isnull=True)
        if opts['grep']:
            rows = rows.filter(Q(key__icontains=opts['grep']) | Q(text__icontains=opts['grep']))
        if opts['backend']:
            rows = rows.filter(backend=opts['backend'])
        rows = list(rows.order_by('created_at'))
        for row in rows:
            self.stdout.write(self.describe(row, hashes))
        self.stdout.write(f'{len(rows)} passage(s).')

    def carry_forward(self, slug, world, hashes, opts):
        current = set(store.live(slug).filter(backend='openrouter').values_list('key', 'packet_hash'))
        current_keys = {k for k, h in current if hashes.get(k) == h}
        stale_keys = sorted({k for k, h in current if k in hashes and hashes[k] != h} - current_keys)
        orphaned = sorted({k for k, h in current if k not in hashes})
        adopted = refused = 0
        for key in stale_keys:
            if opts['apply']:
                ok = store.carry_forward(slug, world, key) is not None
            else:
                stale = (store.live(slug).filter(key=key, backend='openrouter').exclude(packet_hash=hashes[key])
                         .order_by('-created_at').first())
                ok = not narrator.grounding_problems(stale.text, narrator.packet(world, key)[0])
            adopted += ok
            refused += not ok
        verb = ('carried forward', 'retired as stale') if opts['apply'] else ('would carry forward', 'would retire as stale')
        self.stdout.write(f'{len(stale_keys)} LLM passage(s) were written for an older version of their record: '
                          f'{adopted} {verb[0]}, {refused} {verb[1]}.')
        if orphaned:
            self.stdout.write(f'{len(orphaned)} live LLM passage(s) belong to keys this world no longer has '
                              '(a rebuild re-minted its ids); they serve no one and can be retired with --id.')
        if stale_keys and not opts['apply']:
            self.stdout.write('Dry run. Add --apply.')

    # Not named check(): that would override BaseCommand.check, Django's system checks.
    def check_grounding(self, slug, world, hashes, opts):
        rows = [r for r in store.live(slug).filter(backend='openrouter').order_by('id')
                if hashes.get(r.key) == r.packet_hash]
        failing = []
        for row in rows:
            data, _ = narrator.packet(world, row.key)
            problems = narrator.grounding_problems(row.text, data)
            if problems:
                failing.append(row.pk)
                self.stdout.write(self.describe(row, hashes) + '\n    fails: ' + '; '.join(problems))
        self.stdout.write(f'{len(failing)} of {len(rows)} live LLM passage(s) fail the grounding check.')
        if failing and opts['apply']:
            count = store.retire(WorldPassage.objects.filter(pk__in=failing), 'grounding sweep')
            self.stdout.write(self.style.SUCCESS(f'Retired {count}. They will be rewritten on next request.'))
        elif failing:
            self.stdout.write('Dry run. Add --apply to retire them.')
