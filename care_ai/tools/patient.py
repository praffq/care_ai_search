from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai.tools._helpers import serialize_one
from care_ai.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetPatientDemographicsTool(BaseTool):
    name = "get_patient_demographics"
    description = (
        "Return basic demographics (age, sex, blood group, identifiers) for "
        "the current patient. Same shape as the patient retrieve API."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.patient.spec import PatientRetrieveSpec

        return PatientRetrieveSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.resources.patient.spec import PatientRetrieveSpec

        return serialize_one(PatientRetrieveSpec, encounter.patient)
