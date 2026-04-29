"""Tools for active Conditions, split into diagnoses and symptoms.

In CARE the same ``Condition`` model backs both diagnoses and symptoms;
they are distinguished only by the ``category`` field, mirroring the split
between ``DiagnosisViewSet`` and ``SymptomViewSet`` in core. Exposing two
narrowly-scoped tools to the LLM is more reliable than one ambiguous tool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import serialize_list
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


def _active_conditions_qs(encounter: Encounter, categories: list[str]):
    from care.emr.models.condition import Condition

    return (
        Condition.objects.filter(
            patient_id=encounter.patient_id,
            clinical_status="active",
            category__in=categories,
        )
        .exclude(verification_status="entered-in-error")
        .order_by("-created_date")
    )


class GetActiveDiagnosesTool(BaseTool):
    name = "get_active_diagnoses"
    description = (
        "List the patient's active DIAGNOSES (Condition rows with "
        "category in ('encounter_diagnosis','chronic_condition')). "
        "Use this for confirmed clinical diagnoses, not for patient-reported "
        "complaints. Result is wrapped as {items, count, truncated}."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.condition.spec import ConditionReadSpec

        return ConditionReadSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.resources.condition.spec import ConditionReadSpec

        qs = _active_conditions_qs(
            encounter, ["encounter_diagnosis", "chronic_condition"]
        )
        return serialize_list(ConditionReadSpec, qs, limit=100)


class GetActiveSymptomsTool(BaseTool):
    name = "get_active_symptoms"
    description = (
        "List the patient's active SYMPTOMS (Condition rows with "
        "category='problem_list_item', created via the Symptom workflow). "
        "Use this for patient-reported complaints / problems, not for "
        "confirmed diagnoses. Result is wrapped as {items, count, truncated}."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.condition.spec import ConditionReadSpec

        return ConditionReadSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.resources.condition.spec import ConditionReadSpec

        qs = _active_conditions_qs(encounter, ["problem_list_item"])
        return serialize_list(ConditionReadSpec, qs, limit=100)
