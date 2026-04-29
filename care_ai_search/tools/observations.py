"""Tool: get_recent_observations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import now_minus, serialize_list
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetRecentObservationsTool(BaseTool):
    name = "get_recent_observations"
    description = (
        "List observations (vitals, labs) recorded for this encounter within "
        "the last `hours` (1-720). Same shape as the observation list API. "
        "Result is wrapped as {items, count, truncated}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "minimum": 1,
                "maximum": 720,
                "description": "Lookback window in hours. Pass 24 for default.",
            },
        },
        "required": ["hours"],
        "additionalProperties": False,
    }

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.observation.spec import ObservationReadSpec

        return ObservationReadSpec

    def execute(
        self, *, encounter: Encounter, hours: int = 24, **_: Any
    ) -> dict[str, Any]:
        from care.emr.models.observation import Observation
        from care.emr.resources.observation.spec import ObservationReadSpec

        hours = max(1, min(720, hours))
        qs = (
            Observation.objects.filter(
                encounter_id=encounter.pk,
                effective_datetime__gte=now_minus(hours=hours),
            )
            .exclude(status="entered-in-error")
            .order_by("-effective_datetime")
        )
        return serialize_list(ObservationReadSpec, qs, limit=200)
