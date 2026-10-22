"""
Management command to delete old AgentMiss rows in batches.

AgentMiss logs every 404 an AI agent hits. Nothing ever expired it, and by
Oct 2026 the table held 1.2M rows / 461 MB, 606k of them from one crawler
over two days. Logging is now capped per user agent per day (see
fabula_web/urls.py); this keeps a rolling window on top of that. Runs
nightly from the `fabula-cron` Railway service (railway.cron.toml).

Usage:
    python manage.py prune_agent_misses --dry-run
    python manage.py prune_agent_misses --days 60
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from narrative.models import AgentMiss


class Command(BaseCommand):
    help = 'Delete AgentMiss rows older than --days, in batches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Keep this many days of misses (default 30)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help='Rows deleted per statement (default 10000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count old rows without deleting anything',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        cutoff = timezone.now() - timedelta(days=options['days'])
        old = AgentMiss.objects.filter(created_at__lt=cutoff)

        if options['dry_run']:
            self.stdout.write(
                f'{old.count()} of {AgentMiss.objects.count()} agent misses are older '
                f'than {options["days"]} days (dry run, nothing deleted)'
            )
            return

        total = 0
        while True:
            batch = old.values('pk')[:batch_size]
            deleted, _ = AgentMiss.objects.filter(pk__in=batch).delete()
            if not deleted:
                break
            total += deleted
            self.stdout.write(f'  deleted {total}')

        self.stdout.write(self.style.SUCCESS(
            f'Deleted {total} agent misses older than {options["days"]} days'))
