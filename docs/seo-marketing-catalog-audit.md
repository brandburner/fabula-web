# Marketing + catalog SEO audit (T-008, 2026-05)

Companion to [`seo-jsonld-audit.md`](seo-jsonld-audit.md). T-005
covered narrative pages (series / season / episode / event /
character / connection). This audit covers the **non-narrative
surfaces**: marketing pages and the catalog.

## Surfaces in scope

- **Marketing base**: `templates/marketing_base.html`. Children in
  `templates/marketing/` include homepage, product, pricing, about,
  faq, for-production, demo-request, early-access, benchmarks,
  flexible-content, hero-laboratory.
- **Catalog base**: `templates/catalog_base.html`. Children:
  `templates/narrative/catalog.html` (the series-list page).

## Current state — side-by-side

| Concern                       | marketing_base.html | catalog_base.html |
|-------------------------------|:-------------------:|:-----------------:|
| `<meta charset>`              | yes                 | yes               |
| `<meta name="viewport">`      | yes                 | yes               |
| `google-site-verification`    | yes                 | **no**            |
| Dynamic `<title>`             | yes                 | per-page block    |
| `<meta name="description">`   | dynamic (page.meta_description / search_description) | **hardcoded site-wide string** |
| `<link rel="canonical">`      | yes (block override) | **no**            |
| Open Graph type/title/url/site_name | yes           | **no**            |
| Open Graph description        | yes                 | **no**            |
| Open Graph image + fallback   | yes (`fabula-og-default.png`) | **no**    |
| Twitter Card (summary_large_image, title, description) | yes  | **no** |
| JSON-LD `Organization` baseline | yes (in `{% block structured_data %}`) | **no** |
| Per-page JSON-LD overrides    | **none** (no child template overrides the block) | **no** |
| Sitemap inclusion             | (out of scope — flag) | (out of scope — flag) |
| `robots` meta                 | **no**              | **no**            |

## Marketing pages — findings

### 1. `Organization` JSON-LD is minimal

In `marketing_base.html` lines 43-52 the block emits:

```jsonld
{ "@context": "https://schema.org", "@type": "Organization",
  "name": "Fabula", "url": "<site>/",
  "description": "Narrative intelligence for production — the story
  bible that updates itself." }
```

Missing properties that materially help Knowledge Graph and AI
answer engines:

- `logo` — required for Google's company knowledge-panel.
- `sameAs` — list of social URLs (LinkedIn, Twitter/X, etc.) — the
  single highest-leverage Organization signal.
- `contactPoint` — when there's a Demo or Contact page, link them
  here so the entity is reachable in structured form.
- `foundingDate`, `industry`, `slogan` — cheap to add, helps
  schema-aware indexing.
- `address` — even just `addressCountry`.

### 2. No per-page JSON-LD on any marketing child

None of the marketing children (`homepage_page.html`,
`product_page.html`, `pricing_page.html`, `about_page.html`,
`faq_page.html`, `for_production_page.html`, `demo_request_page.html`,
`early_access_page.html`, `benchmarks_page.html`) overrides
`{% block structured_data %}`. That means:

- **Homepage** lacks a `Product` / `SoftwareApplication` block.
  Fabula is presented through the marketing site as a SaaS — the
  canonical schema for SaaS rich-result eligibility is
  `SoftwareApplication` (with `applicationCategory`,
  `operatingSystem`, `offers.Price`) or `Product` (with
  `Offer.priceCurrency` and `Offer.price`). At minimum:
  `SoftwareApplication` with `name`, `applicationCategory`,
  `description`, `url`, `provider.@id` linking to the
  `Organization`.
- **FAQ page** lacks `FAQPage` schema, which is Google's most
  consistent rich-result type. Each FAQ item should be a
  `Question` with `acceptedAnswer.Answer`. Implementation cost is
  low (the FAQ data already exists on the page).
- **Pricing page** lacks `Offer` / `PriceSpecification` markup.
  Even a `Product` with a list of `Offer`s improves price
  rich-result eligibility.
- **About page** lacks `AboutPage`. Cheap drop-in.
- **Contact / Demo / Early Access pages** lack `ContactPage` and a
  `ContactPoint` reference linking back to the Organization.

### 3. `og:image` lacks dimensions / alt

`marketing_base.html:29-31` emits `og:image` but no
`og:image:width`, `og:image:height`, or `og:image:alt`. Twitter,
Slack, LinkedIn, and iMessage cards all downgrade rendering without
dimensions; alt text is an accessibility win and a small SEO win.

The fallback image is `narrative/images/fabula-og-default.png`;
audit confirms the file exists at the repo root as
`fabula-og-default.png` but the `<meta>` references it under the
`static('narrative/images/...')` path. Verify the file is also
present in `narrative/static/narrative/images/` or the fallback
will 404 in production.

### 4. Twitter Card lacks `twitter:image` and `twitter:site`

`twitter:card` is set to `summary_large_image` (which REQUIRES a
`twitter:image`), but no `twitter:image` is emitted. Browsers will
either downgrade the card to a plain link or render a broken
preview. Either add `twitter:image` (copy `og:image`) or change
the card type to `summary`.

Also missing: `twitter:site` (the @-handle of the Fabula account)
— required for full attribution.

### 5. No `robots` meta or `noindex`-able preview surfaces

No marketing page emits `<meta name="robots">`. Acceptable for
production (defaults to "index, follow"), but consider:

- `for_production_page.html`, `demo_request_page.html`, and any
  partner-only page might want `robots="noindex, follow"` if
  they're internal-facing.

## Catalog page — findings

`catalog_base.html` is the biggest single gap in the whole audit.

### 1. Missing every common SEO baseline

No canonical, no Open Graph, no Twitter Card, no JSON-LD, no
dynamic description (only a hardcoded "Explore interactive
narrative graphs from iconic TV series."). Crawlers visiting
`/catalog/` cannot rich-card the page in social media previews or
in Google SERP.

**Recommendation**: refactor `catalog_base.html` to share the same
metadata head as `marketing_base.html` (or include it via
`{% include "_seo_head.html" %}`). One shared partial would
collapse the surface area to maintain.

### 2. The catalog IS an ItemList — but emits no `ItemList` JSON-LD

`/catalog/` lists every TVSeries Fabula publishes. This is the
schema.org `ItemList` use-case: each list item is a `ListItem`
with `position` and `url` pointing at a `TVSeries` `@id`. Doing
so gives AI engines a single canonical "what content does Fabula
publish" answer page. The TVSeries `@id`s already exist (each
`SeriesIndexPage` has a `@id` via T-005's `series_jsonld`).

### 3. Title hardcoded in block override pattern

`<title>{% block title %}Explore{% endblock %} | Fabula</title>` —
the default "Explore" word is repeated on every child template
unless explicitly overridden. Several catalog pages probably
already override it, but verify; an SEO audit catches duplicate
titles fast.

## Cross-cutting findings

1. **`Organization` `@id` not shared.** `marketing_base.html`
   emits an `Organization` block with no `@id`. T-005 noted that
   the per-page narrative templates' `publisher.Organization` also
   has no `@id`. Define one canonical `@id`
   (e.g. `https://fabula.productions/#organization`) and reuse it
   everywhere — Google consolidates entity authority across pages
   only when `@id`s match.
2. **No sitemap.xml** spotted in the audit (out of strict scope,
   but flagged). Confirm `wagtailcore.sitemaps` is wired into
   `urls.py` and that it includes marketing + catalog + narrative
   URLs.
3. **No `BreadcrumbList`** on marketing or catalog. Less impactful
   than on narrative pages but still a small SEO win.
4. **Marketing children inherit the bare Organization block by
   default.** Consider making `{% block structured_data %}`
   append-only or providing a `marketing_jsonld` tag (similar to
   `series_jsonld` in `seo_tags.py`) that each child can call with
   its own schema type.

## Prioritised follow-up list

In order of leverage × cheapness:

1. **`FAQPage` JSON-LD on `faq_page.html`** — Google's most
   reliable rich-result type, drop-in addition. _(new ticket)_
2. **Catalog `ItemList` JSON-LD** — single biggest gap on the
   catalog surface; turns the page into AI-engine-discoverable
   inventory. _(new ticket)_
3. **`SoftwareApplication` or `Product` on the marketing homepage**
   — the canonical SaaS rich-result schema. _(new ticket)_
4. **Backfill catalog_base with the same SEO head as
   marketing_base** — share via a `_seo_head.html` partial.
   _(new ticket)_
5. **Add `logo`, `sameAs`, `contactPoint` to the Organization
   block** in `marketing_base.html`. _(new ticket)_
6. **Add `twitter:image` (mirror `og:image`) + `twitter:site`**
   in `marketing_base.html`. Trivial. _(new ticket)_
7. **Add `og:image:width`, `og:image:height`, `og:image:alt`** for
   social card reliability. _(new ticket)_
8. **`AboutPage` JSON-LD on `about_page.html`** — drop-in.
   _(new ticket)_
9. **`ContactPage` + `ContactPoint` on `demo_request_page.html`
   and `early_access_page.html`** + link back to the Organization
   @id. _(new ticket)_
10. **Define a canonical Organization `@id`** and reuse across all
    surfaces (marketing_base, catalog_base once 4 lands, and the
    per-page `publisher.Organization` blocks identified in T-005).
    Cross-cutting one-line code change. _(new ticket)_

## Out of scope

- Open Graph / Twitter Card on the narrative pages (T-005 territory).
- Sitemap configuration.
- Page-load performance and Core Web Vitals.
- A/B copy testing.
