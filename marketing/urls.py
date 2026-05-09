from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="v2_home"),
    path("engine/", views.EngineView.as_view(), name="v2_engine"),
    path(
        "platform/",
        RedirectView.as_view(pattern_name="v2_engine", permanent=True),
    ),
    path("production/", views.ProductionView.as_view(), name="v2_production"),
    path("about/", views.AboutView.as_view(), name="v2_about"),
    path("investors/", views.InvestorsView.as_view(), name="v2_investors"),
]
