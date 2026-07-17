"""Local staging: dev settings pointed at a prod-clone database.

Used for full-fidelity prod data migrations (restore prod dump →
migrate → import → verify → dump back to prod) so production is only
ever touched by a wipe-and-restore of a verified superset. See
docs/import-workflow.md (prod transfer).
"""
from .dev import *  # noqa: F401,F403

DATABASES['default']['NAME'] = 'fabula_web_staging'  # noqa: F405
