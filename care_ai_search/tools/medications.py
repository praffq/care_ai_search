"""Tool: get_active_medications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import serialize_list
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter

ACTIVE_MEDICATION_STATUSES = ("active", "on-hold", "draft")


class GetActiveMedicationsTool(BaseTool):
    name = "get_active_medications"
    description = (
        "List medication requests on the current encounter that are active "
        "or on-hold. Same shape as the medication-request list API. "
        "Result is wrapped as {items, count, truncated}."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.medication.request.spec import (
            MedicationRequestReadSpec,
        )

        return MedicationRequestReadSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.models.medication_request import MedicationRequest
        from care.emr.resources.medication.request.spec import MedicationRequestReadSpec

        qs = MedicationRequest.objects.filter(
            encounter_id=encounter.pk,
            status__in=ACTIVE_MEDICATION_STATUSES,
        ).order_by("-authored_on")
        return serialize_list(MedicationRequestReadSpec, qs, limit=100)
