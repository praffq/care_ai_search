from django.apps import AppConfig

PLUGIN_NAME = "care_ai_search"


class CareAiSearchConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = "Care AI Search"
    default_auto_field = "django.db.models.BigAutoField"
