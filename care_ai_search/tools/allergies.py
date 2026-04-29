"""Tool: get_active_allergies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import serialize_list
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetActiveAllergiesTool(BaseTool):
    name = "get_active_allergies"
    description = (
        "List active AllergyIntolerance entries for the patient with "
        "criticality. Same shape as the allergy list API. Result is wrapped "
        "as {items, count, truncated}."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.allergy_intolerance.spec import (
            AllergyIntoleranceReadSpec,
        )

        return AllergyIntoleranceReadSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.models.allergy_intolerance import AllergyIntolerance
        from care.emr.resources.allergy_intolerance.spec import (
            AllergyIntoleranceReadSpec,
        )

        qs = (
            AllergyIntolerance.objects.filter(
                patient_id=encounter.patient_id,
                clinical_status="active",
            )
            .exclude(verification_status="entered-in-error")
            .order_by("-created_date")
        )
        return serialize_list(AllergyIntoleranceReadSpec, qs, limit=50)
