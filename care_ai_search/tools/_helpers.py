"""Helpers shared across tool implementations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone


def now_minus(*, hours: int = 0, days: int = 0) -> datetime:
    return timezone.now() - timedelta(hours=hours, days=days)


def serialize_one(spec_cls, obj) -> dict[str, Any]:
    """Serialize a single model instance via a Care ReadSpec."""
    return spec_cls.serialize(obj).to_json()


def serialize_list(spec_cls, queryset, *, limit: int) -> dict[str, Any]:
    """Serialize a queryset via a Care ReadSpec, capped at ``limit`` rows.

    Returns ``{items, truncated, count}`` so the LLM knows when results
    were cut off and can ask for a tighter window.
    """
    rows = list(queryset[: limit + 1])
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [spec_cls.serialize(obj).to_json() for obj in rows],
        "truncated": truncated,
        "count": len(rows),
    }
