"""
Theme context processor for Fabula.

Provides theme selection via session or query parameter.
Switch themes by appending ?theme=writerly or ?theme=dark to any URL.
"""


def theme_context(request):
    """
    Add theme context to all templates.

    Theme is determined by:
    1. ?theme= query parameter (also saves to session)
    2. Session value from previous selection
    3. Default: 'writerly'
    """
    # Check query param first (allows switching via URL)
    theme = request.GET.get('theme')
    if theme in ('dark', 'writerly'):
        request.session['fabula_theme'] = theme
    else:
        theme = request.session.get('fabula_theme', 'writerly')

    return {
        'fabula_theme': theme,
        'is_dark_theme': theme == 'dark',
        'is_writerly_theme': theme == 'writerly',
    }
