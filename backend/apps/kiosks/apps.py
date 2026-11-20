from django.apps import AppConfig


class KiosksConfig(AppConfig):
    name = "apps.kiosks"
    label = "kiosks"
    verbose_name = "Bornes"

    def ready(self) -> None:
        from . import authentication  # noqa: F401  (registers the OpenAPI auth extension)
