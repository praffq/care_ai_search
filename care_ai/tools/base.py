from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from care.emr.models.encounter import Encounter

# Internal/large fields that aren't useful for an LLM picking which tool to call.
# `meta` is already stripped by ``EMRResource.to_json``.
_DESCRIPTION_FIELD_BLOCKLIST = frozenset(
    {
        "meta",
        "extensions",
        "permissions",
        "created_by",
        "updated_by",
        "instance_tags",
        "facility_tags",
        "instance_identifiers",
        "facility_identifiers",
    }
)


class BaseTool:
    """Base class for read-only AI tools.

    Subclasses must define `name`, `description`, `parameters` (JSON Schema for
    LLM-supplied args only — `encounter` is injected by the agent loop and is
    never accepted from the model) and implement `execute`.

    Subclasses *should* implement ``get_response_spec()`` returning the EMR
    ReadSpec used to shape the tool's output. The base class introspects it
    to append the available fields to the tool description so the LLM knows
    what data each tool can surface — making tool selection deterministic
    rather than guesswork.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    # OpenAI strict mode requires `additionalProperties: false` and *all*
    # property keys present in `required`. Tools with optional ints (e.g.
    # `hours`) make the LLM pass them every call — a tiny ergonomic cost
    # in exchange for guaranteed-shape arguments. Set to False per-tool to
    # opt out.
    strict: ClassVar[bool] = True

    @classmethod
    def get_response_spec(cls) -> type[BaseModel] | None:
        """Lazily import + return the EMR ReadSpec describing the tool output.

        Lazy because Care models can't be imported at plugin import time.
        Override per-tool. Return ``None`` to skip auto-field-list generation.
        """
        return None

    def _build_description(self) -> str:
        """Static description plus an auto-generated 'Returns fields:' suffix."""
        spec = self.get_response_spec()
        if spec is None:
            return self.description
        fields = sorted(
            f for f in spec.model_fields if f not in _DESCRIPTION_FIELD_BLOCKLIST
        )
        if not fields:
            return self.description
        return f"{self.description}\n\nReturns fields: {', '.join(fields)}."

    def openai_schema(self) -> dict[str, Any]:
        """Return the function-calling schema for the Chat Completions API."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._build_description(),
                "parameters": self.parameters,
                "strict": self.strict,
            },
        }

    def run(self, encounter: Encounter, **kwargs: Any) -> Any:
        """Entry point used by the agent loop.

        `encounter` is resolved + permission-checked upstream. Subclasses only
        receive whatever LLM-supplied kwargs match their `parameters` schema.
        """
        return self.execute(encounter=encounter, **kwargs)

    def execute(self, *, encounter: Encounter, **kwargs: Any) -> Any:
        raise NotImplementedError
