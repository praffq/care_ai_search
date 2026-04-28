from django.db import models


class SearchQueryLog(models.Model):
    """Smoke-test model: confirms the plugin's app + migrations pipeline works end-to-end."""

    query = models.CharField(max_length=255)
