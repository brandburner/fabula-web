from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_stream, name='chat_stream'),
    path('suggestions/', views.chat_suggestions, name='chat_suggestions'),
]
