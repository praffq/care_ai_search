from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from care.emr.models.encounter import Encounter
from care.security.authorization import AuthorizationController

if TYPE_CHECKING:
    pass


def resolve_encounter(encounter_external_id: str | UUID) -> Encounter:
    """Look up the encounter by external_id, returning 404 if missing."""
    return get_object_or_404(
        Encounter,
        external_id=encounter_external_id,
    )


def authorize_encounter_read(user, encounter: Encounter) -> None:
    """Mirror EncounterViewSet.authorize_retrieve. Raises PermissionDenied on fail."""
    if AuthorizationController.call("can_view_patient_obj", user, encounter.patient):
        return
    if AuthorizationController.call("can_view_encounter_obj", user, encounter):
        return
    raise PermissionDenied("You do not have permission to view this encounter")
