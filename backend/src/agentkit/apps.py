from django.apps import AppConfig


class AgentKitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agentkit"
    verbose_name = "Agent Kit"

    def ready(self):
        from .registry import load_extensions

        load_extensions()
