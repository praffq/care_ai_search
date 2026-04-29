from typing import Any

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver

from care_ai.apps import PLUGIN_NAME

env = environ.Env()


class PluginSettings:
    def __init__(
        self,
        plugin_name: str,
        defaults: dict | None = None,
        required_settings: set | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.defaults = defaults or {}
        self.required_settings = required_settings or set()
        self._cached_attrs: set[str] = set()
        self.validate()

    def __getattr__(self, attr: str) -> Any:
        if attr not in self.defaults:
            raise AttributeError(f"Invalid setting: {attr!r}")

        val = self.defaults[attr]
        try:
            val = self.user_settings[attr]
        except KeyError:
            try:
                if isinstance(val, list):
                    # django-environ's list cast splits on commas, which mangles
                    # JSON arrays. Try JSON first, fall back to CSV.
                    raw = env(attr)
                    try:
                        import json

                        parsed = json.loads(raw)
                        val = parsed if isinstance(parsed, list) else [parsed]
                    except (ValueError, TypeError):
                        val = [s.strip() for s in raw.split(",") if s.strip()]
                else:
                    val = env(attr, cast=type(val) if val is not None else str)
            except environ.ImproperlyConfigured:
                pass

        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    @property
    def user_settings(self) -> dict:
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "PLUGIN_CONFIGS", {}).get(
                self.plugin_name, {}
            )
        return self._user_settings

    def validate(self) -> None:
        for setting in self.required_settings:
            if not getattr(self, setting):
                raise ImproperlyConfigured(
                    f'The "{setting}" setting is required. Set it in the environment '
                    f"or in the {self.plugin_name} plugin config."
                )

    def reload(self) -> None:
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


DEFAULTS = {
    "AI_BASE_URL": "https://api.openai.com/v1",
    "AI_API_KEY": "",
    "AI_DEFAULT_MODEL": "gpt-5.4",
    "AI_ALLOWED_MODELS": [
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.2",
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "AI_MAX_TOOL_CALLS": 10,
    "AI_TIMEOUT_SECONDS": 30,
    "AI_PROMPT_MAX_CHARS": 8000,
}

# AI_API_KEY isn't strictly required at import time — fail at request time instead,
# so the plugin loads cleanly in environments that don't use it (CI, tests).
REQUIRED_SETTINGS: set[str] = set()

plugin_settings = PluginSettings(
    PLUGIN_NAME, defaults=DEFAULTS, required_settings=REQUIRED_SETTINGS
)


@receiver(setting_changed)
def reload_plugin_settings(*args: Any, **kwargs: Any) -> None:
    if kwargs.get("setting") == "PLUGIN_CONFIGS":
        plugin_settings.reload()
