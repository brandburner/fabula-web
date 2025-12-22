# Fabula Web

A Wagtail-powered website for exploring narrative graph analysis from the Fabula system. This site publishes rich narrative data from The West Wing Season 1, making **connections between events first-class content**.

## Key Feature

Unlike traditional websites where links are just navigation, Fabula Web treats narrative connections as addressable content. Each connection has:
- Its own URL (`/connections/123/`)
- A description explaining WHY events connect
- Type classification (Causal, Foreshadowing, Thematic Parallel, etc.)
- Visual encoding with consistent colors and icons

## Tech Stack

- **Backend**: Django 5.1, Wagtail 7.2, PostgreSQL
- **Frontend**: Tailwind CSS, Alpine.js, D3.js
- **Data**: Neo4j → YAML → Wagtail pipeline
- **Deployment**: Railway

## Local Development

```bash
# Create conda environment
conda create -n fabula_wagtail python=3.11
conda activate fabula_wagtail

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Run migrations
DJANGO_SETTINGS_MODULE=fabula_web.settings.dev python manage.py migrate

# Create superuser
DJANGO_SETTINGS_MODULE=fabula_web.settings.dev python manage.py createsuperuser

# Run development server
DJANGO_SETTINGS_MODULE=fabula_web.settings.dev python manage.py runserver
```

## Data Import

```bash
# Export from Neo4j to YAML
python manage.py export_from_neo4j --output ./fabula_export

# Import YAML to Wagtail
python manage.py import_fabula ./fabula_export
```

## Connection Types

| Type | Color | Description |
|------|-------|-------------|
| Causal | Cyan | A directly causes B |
| Foreshadowing | Purple | A hints at B |
| Thematic Parallel | Amber | A and B explore same theme |
| Character Continuity | Emerald | Character state evolves |
| Escalation | Red | B raises stakes from A |
| Callback | Blue | B explicitly references A |
| Emotional Echo | Pink | B evokes same emotion as A |
| Symbolic Parallel | Violet | A and B share symbolic meaning |
| Temporal | Indigo | Time structure connection |

## Deployment

The site is configured for Railway deployment. Push to `main` branch triggers automatic deployment.

```bash
railway login
railway link
railway up
```

## License

MIT
