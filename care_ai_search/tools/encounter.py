from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import now_minus, serialize_list, serialize_one
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetCurrentEncounterTool(BaseTool):
    name = "get_current_encounter"
    description = (
        "Return details (class, status, period, priority, location, care team) "
        "of the current encounter. Same shape as the encounter retrieve API."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.encounter.spec import EncounterRetrieveSpec

        return EncounterRetrieveSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.resources.encounter.spec import EncounterRetrieveSpec

        return serialize_one(EncounterRetrieveSpec, encounter)


class GetPriorEncountersTool(BaseTool):
    name = "get_prior_encounters"
    description = (
        "List the patient's prior encounters within the last `months` "
        "(1-60), excluding the current one. Same shape as the encounter list "
        "API. Result is wrapped as {items, count, truncated}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "months": {
                "type": "integer",
                "minimum": 1,
                "maximum": 60,
                "description": "How many months back to look. Pass 12 for default.",
            },
        },
        "required": ["months"],
        "additionalProperties": False,
    }

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.encounter.spec import EncounterListSpec

        return EncounterListSpec

    def execute(
        self, *, encounter: Encounter, months: int = 12, **_: Any
    ) -> dict[str, Any]:
        from care.emr.models.encounter import Encounter as EncounterModel
        from care.emr.resources.encounter.spec import EncounterListSpec

        months = max(1, min(60, months))
        qs = (
            EncounterModel.objects.filter(
                patient_id=encounter.patient_id,
                created_date__gte=now_minus(days=30 * months),
            )
            .exclude(pk=encounter.pk)
            .order_by("-created_date")
        )
        return serialize_list(EncounterListSpec, qs, limit=50)
