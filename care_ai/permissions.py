from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from care.emr.models.encounter import Encounter

if TYPE_CHECKING:
    pass


class IsSuperuserOnly(IsAuthenticated):
    """Temporary gate: any superuser, no one else."""

    message = (
        "care_ai is restricted to superusers while permissions are wired up"
    )

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and bool(
            getattr(request.user, "is_superuser", False)
        )


def resolve_encounter(encounter_external_id: str | UUID) -> Encounter:
    """Look up the encounter, returning 404 if missing.

    Auth is handled by ``IsSuperuserOnly`` on the view, so by the time we
    get here the caller is already known to be a superuser.
    """
    return get_object_or_404(
        Encounter.objects.select_related("patient", "facility", "current_location"),
        external_id=encounter_external_id,
    )
