from __future__ import annotations

from itertools import count
from typing import Any

import jsonschema
from pydantic import BaseModel, Field, create_model


class InvalidResponseSchema(ValueError):
    """Raised when the supplied output_format is not a valid JSON Schema."""


_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

_model_seq = count(1)


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


def build_pydantic_model(schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from a validated JSON Schema."""
    validate_schema(schema)
    return _build_object_model(schema, name="AgentResponse")


def _build_object_model(schema: dict[str, Any], *, name: str) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    required = set(schema.get("required", []))
    for prop_name, prop in schema.get("properties", {}).items():
        py_type = _resolve_type(prop, parent_name=f"{name}_{prop_name}")
        description = prop.get("description")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(..., description=description))
        else:
            fields[prop_name] = (py_type | None, Field(None, description=description))
    if not fields:
        return create_model(name)
    return create_model(name, **fields)


def _resolve_type(prop: dict[str, Any], *, parent_name: str) -> Any:
    t = prop.get("type")
    if t == "object":
        return _build_object_model(prop, name=f"{parent_name}_{next(_model_seq)}")
    if t == "array":
        items = prop.get("items") or {}
        item_type = _resolve_type(items, parent_name=parent_name) if items else Any
        return list[item_type]
    return _TYPE_MAP.get(t, Any)
