from django.urls import path
from . import views

app_name = 'adventure'
urlpatterns = [
    path('dracula/', views.play, name='play'),
    path('dracula/embed/', views.embed, name='embed'),
    path('api/state/', views.state, name='state'),
    path('api/turn/', views.turn, name='turn'),
    path('dracula/download/', views.export, name='export'),
]
