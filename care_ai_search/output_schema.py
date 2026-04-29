from __future__ import annotations

from itertools import count
from typing import Any

import jsonschema
from pydantic import BaseModel, Field, create_model


class InvalidResponseSchema(ValueError):
    """Raised when the supplied output_format schema is not valid JSON Schema."""


_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

# Used to give nested anonymous object models unique names.
_model_seq = count(1)


_SHORTHAND_LEAF_TYPES: dict[type, str] = {
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
}


def shorthand_to_schema(shorthand: dict[str, Any]) -> dict[str, Any]:
    """Turn a JSON example object into a strict JSON Schema.

    Example::

        {"encounter_id": "string", "allergies": ["string"], "age": 0}

    becomes::

        {
          "type": "object",
          "properties": {
            "encounter_id": {"type": "string"},
            "allergies": {"type": "array", "items": {"type": "string"}},
            "age": {"type": "integer"},
          },
          "required": ["encounter_id", "allergies", "age"],
          "additionalProperties": false,
        }

    Conventions:
      * primitive value -> ``{"type": <inferred>}`` (str/int/float/bool)
      * ``[item]`` -> ``{"type": "array", "items": <schema for item>}``
      * ``{...}`` -> nested object schema (recursive)
      * empty list -> array of any
      * all keys are required
    """
    return _shorthand_object(shorthand)


def _shorthand_object(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidResponseSchema("shorthand must be a JSON object at the root")
    properties: dict[str, Any] = {}
    for key, raw in value.items():
        properties[key] = _shorthand_value(raw, path=key)
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _shorthand_value(value: Any, *, path: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return _shorthand_object(value)
    if isinstance(value, list):
        if not value:
            return {"type": "array"}
        if len(value) > 1:
            raise InvalidResponseSchema(
                f"shorthand array at '{path}' must have exactly one example item"
            )
        return {"type": "array", "items": _shorthand_value(value[0], path=f"{path}[]")}
    # bool first because bool is a subclass of int
    if isinstance(value, bool):
        return {"type": "boolean"}
    for py_type, schema_type in _SHORTHAND_LEAF_TYPES.items():
        if isinstance(value, py_type):
            return {"type": schema_type}
    raise InvalidResponseSchema(
        f"shorthand at '{path}' has unsupported value of type {type(value).__name__}"
    )


def extract_schema(output_format: dict[str, Any]) -> dict[str, Any]:
    """Pull the inner JSON Schema out of a caller-supplied ``output_format``.

    Accepts three shapes:
      * full OpenAI envelope:
          ``{"type": "json_schema", "json_schema": {"name": ..., "schema": {...}}}``
      * bare JSON Schema:
          ``{"type": "object", "properties": {...}, ...}``
      * shorthand example dict (no ``type`` key):
          ``{"encounter_id": "string", "allergies": ["string"]}``
    """
    if not isinstance(output_format, dict):
        raise InvalidResponseSchema("output_format must be a JSON object")
    inner = output_format.get("json_schema")
    if isinstance(inner, dict) and "schema" in inner:
        return inner["schema"]
    if output_format.get("type") == "object":
        return output_format
    if "type" not in output_format:
        return shorthand_to_schema(output_format)
    raise InvalidResponseSchema(
        "output_format must be one of: an OpenAI response_format envelope "
        "({type: json_schema, json_schema: {schema: ...}}), a bare JSON Schema "
        "with type=object at the root, or a shorthand example object."
    )


def validate_response_schema(schema: dict[str, Any]) -> None:
    """Reject malformed JSON Schemas before we hand them to the model."""
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise InvalidResponseSchema(str(exc)) from exc
    if schema.get("type") != "object":
        raise InvalidResponseSchema("response schema must have type=object at the root")


def build_pydantic_model(schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model that mirrors a (validated) JSON Schema."""
    validate_response_schema(schema)
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
        # create_model rejects an empty kwargs set; give it a sentinel.
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
