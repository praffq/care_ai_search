from __future__ import annotations

from typing import Any

import jsonschema


class InvalidResponseSchema(ValueError):
    """Raised when the supplied output_format is not a valid JSON Schema."""


def validate_schema(schema: dict[str, Any]) -> None:
    """Validate that the input is a well-formed JSON Schema with type=object at root."""
    if not isinstance(schema, dict):
        raise InvalidResponseSchema("output_format must be a JSON object")
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise InvalidResponseSchema(str(exc)) from exc
    if schema.get("type") != "object":
        raise InvalidResponseSchema("output_format must have type=object at the root")
