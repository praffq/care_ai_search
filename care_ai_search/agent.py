from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from pydantic import ValidationError

from care_ai_search.output_schema import (
    InvalidResponseSchema,
    build_pydantic_model,
)
from care_ai_search.settings import plugin_settings
from care_ai_search.tools import TOOLS

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base class for agent-loop failures."""


class ToolCallBudgetExceededError(AgentError):
    pass


class AgentTimeoutError(AgentError):
    pass


class OutputValidationError(AgentError):
    pass


@dataclass
class AgentResult:
    data: dict[str, Any]
    model: str
    tool_call_count: int
    latency_ms: int
    raw_response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


def _build_client() -> OpenAI:
    api_key = plugin_settings.AI_API_KEY
    if not api_key:
        msg = (
            "AI_API_KEY is not set. Configure it in plug_config.py PLUGIN_CONFIGS "
            "or set the AI_API_KEY environment variable."
        )
        raise AgentError(msg)
    return OpenAI(
        api_key=api_key,
        base_url=plugin_settings.AI_BASE_URL,
        timeout=plugin_settings.AI_TIMEOUT_SECONDS,
    )


def _dispatch_tool_call(encounter: Encounter, name: str, raw_args: str) -> Any:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool: {name}"}
    try:
        kwargs = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError:
        return {"error": "tool arguments were not valid JSON"}
    try:
        return tool.run(encounter=encounter, **kwargs)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception:
        logger.exception("Tool %s failed", name)
        return {"error": f"tool {name} raised an internal error"}


def run_agent(
    *,
    encounter: Encounter,
    prompt: str,
    output_format: dict[str, Any],
    model: str | None = None,
    max_tool_calls: int | None = None,
) -> AgentResult:
    """Run the tool-calling loop until the model produces a structured response.

    Raises:
        AgentError: API key missing or other unrecoverable issue.
        ToolCallBudgetExceededError: model kept calling tools past the cap.
        AgentTimeoutError: total wall-clock time exceeded.
        OutputValidationError: model's final answer didn't match output_format.
    """
    started_at = time.monotonic()
    timeout_s = plugin_settings.AI_TIMEOUT_SECONDS
    cap = min(
        max_tool_calls or plugin_settings.AI_MAX_TOOL_CALLS,
        plugin_settings.AI_MAX_TOOL_CALLS,
    )
    chosen_model = model or plugin_settings.AI_DEFAULT_MODEL

    # Build the pydantic model up-front so a malformed schema fails fast,
    # before we call the model. Always rewrap the inner schema in the OpenAI
    # ``response_format`` envelope so callers can pass shorthand / bare schemas
    # without us forwarding a non-OpenAI shape to the API.
    try:
        response_model = build_pydantic_model(output_format)
    except InvalidResponseSchema as exc:
        raise OutputValidationError(f"invalid output_format: {exc}") from exc
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "agent_response", "schema": output_format},
    }

    client = _build_client()
    tool_schemas = [t.openai_schema() for t in TOOLS.values()]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": f"Encounter id (already scoped): {encounter.external_id}",
        },
    ]
    tool_trace: list[dict[str, Any]] = []
    tool_call_count = 0
    input_tokens = output_tokens = 0

    for _ in range(cap + 1):
        if time.monotonic() - started_at > timeout_s:
            raise AgentTimeoutError(f"agent loop exceeded {timeout_s}s")

        response = client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            tools=tool_schemas,
            response_format=response_format,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            output_tokens += getattr(usage, "completion_tokens", 0) or 0

        msg = response.choices[0].message
        # Append the assistant turn so subsequent tool messages have a parent.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (msg.tool_calls or [])
                ]
                or None,
            }
        )

        if not msg.tool_calls:
            try:
                parsed = response_model.model_validate_json(msg.content or "{}")
            except ValidationError as exc:
                raise OutputValidationError(str(exc)) from exc
            except json.JSONDecodeError as exc:
                raise OutputValidationError(
                    f"model returned non-JSON content: {exc}"
                ) from exc
            return AgentResult(
                data=parsed.model_dump(mode="json"),
                model=chosen_model,
                tool_call_count=tool_call_count,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                raw_response_text=msg.content or "",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_trace=tool_trace,
            )

        for tc in msg.tool_calls:
            if tool_call_count >= cap:
                raise ToolCallBudgetExceededError(f"tool-call budget of {cap} exceeded")
            tool_call_count += 1
            result = _dispatch_tool_call(
                encounter, tc.function.name, tc.function.arguments
            )
            tool_trace.append(
                {"name": tc.function.name, "arguments": tc.function.arguments}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    raise ToolCallBudgetExceededError(f"loop exceeded {cap} iterations")
