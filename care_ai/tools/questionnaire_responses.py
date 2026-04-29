from __future__ import annotations

from typing import TYPE_CHECKING, Any

from care_ai.tools.base import BaseTool

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter


class GetQuestionnaireResponsesTool(BaseTool):
    """Submitted questionnaire responses (forms) for the current encounter.

    Useful for computing scores (NEWS2, GCS, qSOFA, MEWS, pain scales) or
    pulling specific values out of structured forms.
    """

    name = "get_questionnaire_responses"
    description = (
        "List submitted QuestionnaireResponse entries (forms) for the current "
        "encounter. Each item includes the questionnaire title/slug, status, "
        "who submitted it, when, and a list of question/answer pairs from "
        "render_responses(). Useful for computing scores (NEWS2, GCS, qSOFA, "
        "MEWS, pain scales) or pulling specific values out of structured forms. "
        "Result is wrapped as {items, count, truncated}."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Max number of responses to return. Pass 50 for default.",
            },
        },
        "required": ["limit"],
        "additionalProperties": False,
    }

    @classmethod
    def get_response_spec(cls):
        return None

    def execute(
        self, *, encounter: Encounter, limit: int = 50, **_: Any
    ) -> dict[str, Any]:
        from care.emr.models.questionnaire import QuestionnaireResponse

        limit = max(1, min(200, limit))
        qs = (
            QuestionnaireResponse.objects.select_related("questionnaire", "created_by")
            .filter(encounter_id=encounter.pk)
            .order_by("-created_date")
        )
        rows = list(qs[: limit + 1])
        truncated = len(rows) > limit
        rows = rows[:limit]

        items: list[dict[str, Any]] = []
        for r in rows:
            q = r.questionnaire
            items.append(
                {
                    "id": str(r.external_id),
                    "questionnaire": {
                        "id": str(q.external_id) if q else None,
                        "slug": q.slug if q else None,
                        "title": q.title if q else None,
                    },
                    "status": r.status,
                    "submitted_at": r.created_date.isoformat()
                    if r.created_date
                    else None,
                    "submitted_by": (
                        r.created_by.username if r.created_by_id else None
                    ),
                    "responses": r.render_responses(),
                }
            )
        return {"items": items, "count": len(items), "truncated": truncated}
