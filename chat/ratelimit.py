"""
Per-IP dual-window rate limiting on the Django cache.

Launch-blocking by design (brief §4.6): the sister project shipped its chat
with zero rate limiting and no cost caps and had to file it as a critical
incident later. Fabula launches with both. Production's default cache is a
shared DatabaseCache, so limits hold across gunicorn workers (avoiding the
prior art's per-worker LocMem caveat); dev's LocMemCache is fine locally.
"""

from django.conf import settings
from django.core.cache import cache

WINDOWS = (
    ('m', 60, 'CHAT_RATE_LIMIT_PER_MINUTE'),
    ('h', 3600, 'CHAT_RATE_LIMIT_PER_HOUR'),
)


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def check_rate_limit(request):
    """Fixed-window counters. Returns (allowed: bool, retry_after: int)."""
    ip = client_ip(request)
    for suffix, ttl, setting_name in WINDOWS:
        limit = getattr(settings, setting_name)
        key = f'chat:rl:{suffix}:{ip}'
        cache.add(key, 0, timeout=ttl)
        try:
            count = cache.incr(key)
        except ValueError:
            # Key expired between add and incr — recreate.
            cache.add(key, 1, timeout=ttl)
            count = 1
        if count > limit:
            return False, ttl
    return True, 0
