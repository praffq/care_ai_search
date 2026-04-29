from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai.tools._helpers import now_minus, serialize_list
from care_ai.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetMedicationAdministrationsTool(BaseTool):
    name = "get_medication_administrations"
    description = (
        "List MedicationAdministration records (actual doses given) on the "
        "current encounter within the last `hours` (1-720). Distinct from "
        "get_active_medications, which lists prescriptions/orders. Useful "
        "for confirming what was actually administered, when, and by whom. "
        "Result is wrapped as {items, count, truncated}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "minimum": 1,
                "maximum": 720,
                "description": "Lookback window in hours. Pass 72 for default.",
            },
        },
        "required": ["hours"],
        "additionalProperties": False,
    }

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.medication.administration.spec import (
            MedicationAdministrationReadSpec,
        )

        return MedicationAdministrationReadSpec

    def execute(
        self, *, encounter: Encounter, hours: int = 72, **_: Any
    ) -> dict[str, Any]:
        from care.emr.models.medication_administration import MedicationAdministration
        from care.emr.resources.medication.administration.spec import (
            MedicationAdministrationReadSpec,
        )

        hours = max(1, min(720, hours))
        qs = MedicationAdministration.objects.filter(
            encounter_id=encounter.pk,
            created_date__gte=now_minus(hours=hours),
        ).order_by("-created_date")
        return serialize_list(MedicationAdministrationReadSpec, qs, limit=200)
