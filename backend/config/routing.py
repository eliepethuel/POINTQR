"""WebSocket routes. Real-time consumers are registered here by each app."""

from django.urls import URLPattern, URLResolver

websocket_urlpatterns: list[URLPattern | URLResolver] = []
