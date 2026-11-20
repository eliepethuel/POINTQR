"""WebSocket routes."""

from django.urls import URLPattern, URLResolver, path

from apps.attendance.consumers import DashboardConsumer

websocket_urlpatterns: list[URLPattern | URLResolver] = [
    path("ws/dashboard/", DashboardConsumer.as_asgi()),
]
