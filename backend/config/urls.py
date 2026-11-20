from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("", include("apps.system.urls")),
]

urlpatterns = [
    path("api/v1/", include((api_v1, "v1"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
