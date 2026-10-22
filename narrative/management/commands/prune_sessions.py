"""
Management command to delete expired sessions in batches.

Django's `clearsessions` issues one DELETE for every expired row. By Oct
2026 prod had ~7M expired rows (crawler-minted theme sessions that nothing
ever cleared), and one statement that size holds a long transaction and,
run over the Railway TCP proxy, can outlive the proxy's connection limit.
This deletes the same rows in short, independently committed batches, so
an interrupted run keeps its progress and can simply be re-run.

Usage:
    python manage.py prune_sessions --dry-run
    python manage.py prune_sessions --batch-size 20000
"""

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete expired django_session rows in batches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help='Rows deleted per statement (default 10000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count expired sessions without deleting anything',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        cutoff = timezone.now()
        expired = Session.objects.filter(expire_date__lt=cutoff)

        if options['dry_run']:
            self.stdout.write(
                f'{expired.count()} expired of {Session.objects.count()} sessions '
                f'(dry run, nothing deleted)'
            )
            return

        total = 0
        while True:
            batch = expired.values('pk')[:batch_size]
            deleted, _ = Session.objects.filter(pk__in=batch).delete()
            if not deleted:
                break
            total += deleted
            self.stdout.write(f'  deleted {total}')

        self.stdout.write(self.style.SUCCESS(f'Deleted {total} expired sessions'))
