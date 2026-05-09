from django.views.generic import TemplateView


class V2MarketingView(TemplateView):
    """Renders one of the v2 marketing pages.

    Subclasses set `template_name` and `active_nav` so the shared
    base template can highlight the current nav item.
    """

    active_nav = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = self.active_nav
        return ctx


class HomeView(V2MarketingView):
    template_name = "marketing/v2/home.html"
    active_nav = "home"


class EngineView(V2MarketingView):
    template_name = "marketing/v2/engine.html"
    active_nav = "engine"


class ProductionView(V2MarketingView):
    template_name = "marketing/v2/production.html"
    active_nav = "production"


class AboutView(V2MarketingView):
    template_name = "marketing/v2/about.html"
    active_nav = "about"


class InvestorsView(V2MarketingView):
    template_name = "marketing/v2/investors.html"
    active_nav = "investors"
