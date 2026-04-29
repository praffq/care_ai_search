"""Tool: get_service_requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai_search.tools._helpers import serialize_list
from care_ai_search.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter

OPEN_SR_STATUSES = ("draft", "active", "on-hold")


class GetServiceRequestsTool(BaseTool):
    name = "get_service_requests"
    description = (
        "List open service requests (investigations, referrals) on the "
        "current encounter. Same shape as the service-request list API. "
        "Result is wrapped as {items, count, truncated}."
    )

    @classmethod
    def get_response_spec(cls):
        from care.emr.resources.service_request.spec import ServiceRequestReadSpec

        return ServiceRequestReadSpec

    def execute(self, *, encounter: Encounter, **_: Any) -> dict[str, Any]:
        from care.emr.models.service_request import ServiceRequest
        from care.emr.resources.service_request.spec import ServiceRequestReadSpec

        qs = ServiceRequest.objects.filter(
            encounter_id=encounter.pk,
            status__in=OPEN_SR_STATUSES,
        ).order_by("-created_date")
        return serialize_list(ServiceRequestReadSpec, qs, limit=100)
