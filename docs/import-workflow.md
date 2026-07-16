# Operator runbook: importing narrative data

This is the runbook for loading exported YAML data into a Wagtail
database — single series, multiple series, partial re-imports, and
full series-tree deletion. Pairs with
[`MEGAGRAPH_INGESTION_SPEC.md`](MEGAGRAPH_INGESTION_SPEC.md) (the
source-side exporter spec) and [`seo-analytics-setup.md`](seo-analytics-setup.md).

## TL;DR

```bash
export DJANGO_SETTINGS_MODULE=fabula_web.settings.dev

# Single series, additive (idempotent on fabula_uuid).
python manage.py import_fabula ./fabula_export/westwing

# Series + prune deprecated rows. Preview first.
python manage.py import_fabula ./fabula_export/westwing --cleanup --dry-run
python manage.py import_fabula ./fabula_export/westwing --cleanup
```

## Prerequisites

- Conda env active and pip dependencies installed (see
  [README.md](../README.md) > Local Development).
- Dev Postgres running. Start with:
  ```bash
  /opt/homebrew/anaconda3/envs/fabula_wagtail/bin/pg_ctl \
      -D ~/.local/share/fabula_web/pgdata \
      -l ~/.local/share/fabula_web/pgdata/server.log start
  ```
- `DJANGO_SETTINGS_MODULE=fabula_web.settings.dev` exported (every
  `manage.py` invocation needs it).
- A `./fabula_export/<series>/` directory containing the per-series
  YAML files produced by `manage.py export_from_neo4j` (see
  MEGAGRAPH_INGESTION_SPEC.md for what those files look like).

## Single-series import

```bash
python manage.py import_fabula ./fabula_export/<series>
```

The importer is **idempotent on `fabula_uuid`**. Re-running it
updates existing rows in place rather than duplicating them. You can
also re-export and re-import freely without `--cleanup` — only
authoritative rows change.

Use `--dry-run` to validate the YAML without writing anything.

## Multi-series import

Just run the single-series command once per export directory. The
ordering of series imports doesn't matter — each series's rows are
keyed by `fabula_uuid` and live in their own subtree of Wagtail
pages.

```bash
for series in westwing startrektng doctorwho; do
  python manage.py import_fabula ./fabula_export/$series
done
```

> **Historical note.** Before 2026-05 (ISS-001 / T-001),
> `--cleanup` was global: it deleted every page and snippet whose
> `fabula_uuid` was not in *this* import's canonical set, including
> rows from other series. The operator advice at the time was
> "NEVER use `--cleanup` when importing one series at a time."
> That hazard is gone — `--cleanup` is now strictly series-scoped.
> If you find that warning in old git/issue history, this is why
> it no longer applies.

## Pruning deprecated rows with `--cleanup`

`--cleanup` deletes deprecated rows *within the series being
imported* — rows whose `fabula_uuid` no longer appears in the
canonical export. Other series in the database are never touched.

Always preview first:

```bash
python manage.py import_fabula ./fabula_export/<series> --cleanup --dry-run
```

The dry-run prints a per-model summary (`EventPage`, `EpisodePage`,
`SeasonPage`, `CharacterPage`, `OrganizationPage`, `Location`)
showing `canonical` (in the export), `in_scope` (in the series),
and `deprecated` (would be deleted). Nothing is touched.

When the numbers look right, apply:

```bash
python manage.py import_fabula ./fabula_export/<series> --cleanup
```

After printing the plan, the command asks you to type `delete` to
confirm. Non-interactive runs (scripts, CI) must pass `--yes` or the
cleanup refuses and exits without deleting:

```bash
python manage.py import_fabula ./fabula_export/<series> --cleanup --yes
```

Before deleting, a preflight checks for canonical events that still
reference deprecated episodes (the `PROTECT` FK would abort the
transaction mid-way). If any exist, cleanup refuses up-front, lists
the offending events, and deletes nothing — usually this means the
export's episode UUIDs changed while its events did not; re-export
the series.

The delete phase runs inside a single `transaction.atomic()`: an
unexpected mid-loop failure rolls back the *entire* cleanup phase.
You will not see a half-cleaned database.

## Verifying the import

Quick post-import sanity:

```bash
python manage.py shell -c "
from narrative.models import (
    EventPage, EpisodePage, CharacterPage, SeriesIndexPage,
)
s = SeriesIndexPage.objects.get(fabula_uuid='<series-uuid>')
print('Episodes:', EpisodePage.objects.filter(path__startswith=s.path).count())
print('Events:  ', EventPage.objects.filter(path__startswith=s.path).count())
print('Chars:   ', CharacterPage.objects.filter(path__startswith=s.path).count())
"
```

Compare to the row counts in the YAML if you want a stricter check.

> **About duplicate YAML rows.** Cypher `OPTIONAL MATCH` against
> organisations / participations causes JOIN fan-out, so the YAML
> may contain the same `fabula_uuid` multiple times. The importer's
> `dedupe_by_global_id` step collapses these before the page tree
> is written. YAML row count > database row count is **expected**
> and is not a bug.

Finally, browse the Wagtail admin at
[`http://localhost:8000/admin/`](http://localhost:8000/admin/) to
spot-check titles, descriptions, and a few `NarrativeConnection`
URLs.

## Deleting a whole series tree

Use the `delete_series` command — it handles the two-stage order
(`series.delete()` alone fails because `EventPage.episode` is a
`PROTECT` foreign key; events must go first). Snippets (`Location`,
`Theme`, `ConflictArc`) cascade automatically via `series`
`on_delete=CASCADE`, and connections/participations/profiles cascade
from events and episodes.

```bash
# Preview what would be deleted (per-model counts):
python manage.py delete_series <slug-or-fabula_uuid> --dry-run

# Apply (interactive: asks you to type the series slug to confirm;
# non-interactive runs require --yes):
python manage.py delete_series <slug-or-fabula_uuid> --yes
```

Both stages run inside one `transaction.atomic()` — a failure
anywhere rolls the whole deletion back. Other series are never
touched.

If you only need to prune *deprecated* rows within a series rather
than delete the whole series, use `--cleanup` instead — it's safer
and idempotent.

## Production transfer

The Railway production database is reachable but the public TCP
proxy times out for long-running connections (~70 min), so
`import_fabula` does not work against it directly. The supported
path is:

1. Import locally into your dev Postgres.
2. `pg_dump -Fc fabula_web > fabula.dump`
3. `pg_restore` into the Railway database via its public URL
   (`crossover.proxy.rlwy.net:53085`) or from a Railway shell.

Don't try to run `import_fabula` against production — the
transaction will roll back when the proxy disconnects.

## Related

- [README.md](../README.md) — orientation and tech stack.
- [MEGAGRAPH_INGESTION_SPEC.md](MEGAGRAPH_INGESTION_SPEC.md) —
  Neo4j source-side schema and exporter contract.
- [seo-analytics-setup.md](seo-analytics-setup.md) — SEO and
  analytics configuration.
