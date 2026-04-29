from django.conf import settings
from django.db import models

from care.utils.models.base import BaseModel


class AIRunAuditLog(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_runs",
    )
    encounter = models.ForeignKey(
        "emr.Encounter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_runs",
    )
    model = models.CharField(max_length=64)
    prompt_hash = models.CharField(max_length=64)
    response_hash = models.CharField(max_length=64)
    tool_call_count = models.PositiveIntegerField()
