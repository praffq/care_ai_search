from care_ai_search.tools.allergies import GetActiveAllergiesTool
from care_ai_search.tools.base import BaseTool
from care_ai_search.tools.conditions import (
    GetActiveDiagnosesTool,
    GetActiveSymptomsTool,
)
from care_ai_search.tools.encounter import (
    GetCurrentEncounterTool,
    GetPriorEncountersTool,
)
from care_ai_search.tools.medications import GetActiveMedicationsTool
from care_ai_search.tools.observations import GetRecentObservationsTool
from care_ai_search.tools.patient import GetPatientDemographicsTool
from care_ai_search.tools.service_requests import GetServiceRequestsTool

TOOL_CLASSES: list[type[BaseTool]] = [
    GetPatientDemographicsTool,
    GetCurrentEncounterTool,
    GetActiveAllergiesTool,
    GetActiveDiagnosesTool,
    GetActiveSymptomsTool,
    GetRecentObservationsTool,
    GetActiveMedicationsTool,
    GetServiceRequestsTool,
    GetPriorEncountersTool,
]

TOOLS: dict[str, BaseTool] = {cls.name: cls() for cls in TOOL_CLASSES}


__all__ = ["TOOLS", "TOOL_CLASSES", "BaseTool"]
