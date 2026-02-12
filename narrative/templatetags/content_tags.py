"""
Content Template Tags

Template tags for loading YAML content files and rendering marketing pages.

Usage in templates:
    {% load content_tags %}
    {% load_content 'platform' as page %}
    {{ page.hero.headline }}
"""

import logging
import os

import yaml
from django import template
from django.conf import settings

register = template.Library()
logger = logging.getLogger(__name__)


@register.simple_tag
def load_content(slug):
    """Load YAML content file for a marketing page.

    Usage: {% load_content 'platform' as page %}

    Returns a dict parsed from content/<slug>.yaml.
    Returns empty dict on missing file or parse error.
    """
    content_dir = os.path.join(settings.BASE_DIR, 'content')
    file_path = os.path.join(content_dir, f'{slug}.yaml')
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("Content file not found: %s", file_path)
        return {}
    except yaml.YAMLError as e:
        logger.error("YAML parse error in %s: %s", file_path, e)
        return {}


@register.filter
def accent_color(color_name):
    """Map a YAML color name to the CSS custom property.

    Usage: {{ feature.color|accent_color }}
    Returns: var(--f-accent-primary)
    """
    valid = {'primary', 'green', 'blue', 'violet', 'orange', 'cyan', 'rose'}
    color = color_name if color_name in valid else 'primary'
    return f'var(--f-accent-{color})'


@register.filter
def accent_bg(color_name):
    """Map a YAML color name to the CSS background custom property.

    Usage: {{ feature.color|accent_bg }}
    Returns: var(--f-accent-primary-bg)
    """
    valid = {'primary', 'green', 'blue', 'violet', 'orange', 'cyan', 'rose'}
    color = color_name if color_name in valid else 'primary'
    return f'var(--f-accent-{color}-bg)'


@register.filter
def section_bg(background):
    """Map a YAML background name to the CSS background value.

    Usage: style="background: {{ section.background|section_bg }}"
    """
    bg_map = {
        'page': 'var(--f-bg-page)',
        'surface': 'var(--f-bg-surface)',
        'hero': 'var(--f-bg-hero)',
        'elevated': 'var(--f-bg-elevated)',
    }
    return bg_map.get(background, 'var(--f-bg-page)')
