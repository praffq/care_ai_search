from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openai import APITimeoutError, OpenAI, RateLimitError

from care_ai.output_schema import InvalidResponseSchema, validate_schema
from care_ai.settings import plugin_settings
from care_ai.tools import TOOLS

if TYPE_CHECKING:
    from care.emr.models.encounter import Encounter

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base class for agent-loop failures."""


class ToolCallBudgetExceededError(AgentError):
    """Raised when the model keeps calling tools past `max_tool_iterations`."""


class AgentTimeoutError(AgentError):
    """Raised when the local wall-clock budget is exhausted."""


class UpstreamTimeoutError(AgentError):
    """Raised when the OpenAI client itself times out."""


class RateLimitedError(AgentError):
    """Raised when the upstream LLM provider rate-limits the request."""


class OutputValidationError(AgentError):
    """Raised when the model's final answer doesn't match `response_schema`."""


@dataclass
class AgentResult:
    output: Any
    model: str
    tool_call_count: int
    duration_ms: int
    raw_response_text: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


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


def _build_response_format(response_schema: dict[str, Any] | None):
    if response_schema is None:
        return None
    try:
        validate_schema(response_schema)
    except InvalidResponseSchema as exc:
        raise OutputValidationError(f"invalid response_schema: {exc}") from exc
    return {
        "type": "json_schema",
        "json_schema": {"name": "agent_response", "schema": response_schema},
    }


def run_agent(
    *,
    encounter: Encounter,
    prompt: str,
    response_schema: dict[str, Any] | None = None,
    model: str | None = None,
    max_tool_iterations: int | None = None,
) -> AgentResult:
    """Run the tool-calling loop until the model produces a final response.

    Raises:
        AgentError: API key missing or other unrecoverable issue.
        ToolCallBudgetExceededError: model kept calling tools past the cap.
        AgentTimeoutError: total wall-clock time exceeded.
        UpstreamTimeoutError: the OpenAI HTTP client itself timed out.
        RateLimitedError: upstream provider rate-limited the request.
        OutputValidationError: model's final answer didn't match response_schema.
    """
    started_at = time.monotonic()
    timeout_s = plugin_settings.AI_TIMEOUT_SECONDS
    cap = min(
        max_tool_iterations or plugin_settings.AI_MAX_TOOL_CALLS,
        plugin_settings.AI_MAX_TOOL_CALLS,
    )
    chosen_model = model or plugin_settings.AI_DEFAULT_MODEL

    response_format = _build_response_format(response_schema)

    client = _build_client()
    tool_schemas = [t.openai_schema() for t in TOOLS.values()]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": plugin_settings.AI_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    tool_calls_trace: list[dict[str, Any]] = []
    tool_call_count = 0
    input_tokens = output_tokens = 0

    for _ in range(cap + 1):
        if time.monotonic() - started_at > timeout_s:
            raise AgentTimeoutError(f"agent loop exceeded {timeout_s}s")

        request_kwargs: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "tools": tool_schemas,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format

        try:
            response = client.chat.completions.create(**request_kwargs)
        except APITimeoutError as exc:
            raise UpstreamTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise RateLimitedError(str(exc)) from exc

        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            output_tokens += getattr(usage, "completion_tokens", 0) or 0

        msg = response.choices[0].message
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
            text = msg.content or ""
            if response_format is None:
                output: Any = text
            else:
                try:
                    output = json.loads(text or "{}")
                except json.JSONDecodeError as exc:
                    raise OutputValidationError(
                        f"model returned non-JSON content: {exc}"
                    ) from exc
            return AgentResult(
                output=output,
                model=chosen_model,
                tool_call_count=tool_call_count,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                raw_response_text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_calls=tool_calls_trace,
            )

        for tc in msg.tool_calls:
            if tool_call_count >= cap:
                raise ToolCallBudgetExceededError(f"tool-call budget of {cap} exceeded")
            tool_call_count += 1
            result = _dispatch_tool_call(
                encounter, tc.function.name, tc.function.arguments
            )
            tool_calls_trace.append(
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
