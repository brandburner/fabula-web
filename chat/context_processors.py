from django.conf import settings


def chat_settings(request):
    return {'chat_enabled': settings.CHAT_ENABLED}
