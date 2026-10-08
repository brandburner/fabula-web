from django.urls import path
from . import views

app_name = 'adventure'
urlpatterns = [
    # The authored Dracula prototype keeps its original routes and session key.
    path('dracula/', views.play, name='play'),
    path('dracula/embed/', views.embed, name='embed'),
    path('api/state/', views.state, name='state'),
    path('api/turn/', views.turn, name='turn'),
    path('dracula/download/', views.export, name='export'),
    # Projected worlds, configured in settings.ADVENTURE_WORLDS.
    path('<slug:slug>/', views.play, name='world'),
    path('<slug:slug>/embed/', views.embed, name='world_embed'),
    path('<slug:slug>/api/state/', views.state, name='world_state'),
    path('<slug:slug>/api/turn/', views.turn, name='world_turn'),
    path('<slug:slug>/download/', views.export, name='world_export'),
]
