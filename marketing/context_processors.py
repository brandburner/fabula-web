"""
Context processors for the Fabula marketing site.

Provides series context to all templates for navigation and branding.
"""

from narrative.models import SeriesIndexPage


def series_context(request):
    """
    Add current series context to all templates.

    This enables templates to:
    - Show the current series name in header/footer
    - Provide navigation to other series
    - Scope content appropriately

    The current series is determined by:
    1. URL path containing /explore/<series-slug>/
    2. Fallback to first available series
    """
    context = {
        'current_series': None,
        'available_series': [],
    }

    # Get all live series
    available_series = SeriesIndexPage.objects.live()
    context['available_series'] = available_series

    # Try to determine current series from URL
    path = request.path
    if '/explore/' in path:
        # Extract series slug from path: /explore/<slug>/...
        parts = path.split('/explore/')
        if len(parts) > 1:
            remaining = parts[1].strip('/')
            if remaining:
                series_slug = remaining.split('/')[0]
                try:
                    context['current_series'] = available_series.get(slug=series_slug)
                except SeriesIndexPage.DoesNotExist:
                    pass

    # If no series found from URL, try to get from page context
    # This will be handled by the page's get_context method

    return context
