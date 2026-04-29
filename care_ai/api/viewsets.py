import hashlib

from rest_framework.response import Response
from rest_framework.views import APIView

from care_ai.agent import (
    AgentError,
    AgentTimeoutError,
    OutputValidationError,
    ToolCallBudgetExceededError,
    run_agent,
)
from care_ai.api.serializers import RunAIRequestSerializer
from care_ai.models import AIRunAuditLog
from care_ai.permissions import IsSuperuserOnly, resolve_encounter


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RunAIView(APIView):
    permission_classes = [IsSuperuserOnly]

    def post(self, request, *args, **kwargs):
        serializer = RunAIRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data

        encounter = resolve_encounter(body["encounter_id"])

        try:
            result = run_agent(
                encounter=encounter,
                prompt=body["prompt"],
                output_format=body["output_format"],
                model=body.get("model") or None,
                max_tool_calls=body.get("max_tool_calls"),
            )
        except ToolCallBudgetExceededError as exc:
            return Response(
                {"error": "tool_budget_exceeded", "detail": str(exc)}, status=429
            )
        except AgentTimeoutError as exc:
            return Response({"error": "timeout", "detail": str(exc)}, status=504)
        except OutputValidationError as exc:
            return Response(
                {"error": "invalid_model_output", "detail": str(exc)}, status=502
            )
        except AgentError as exc:
            return Response({"error": "agent_error", "detail": str(exc)}, status=500)

        AIRunAuditLog.objects.create(
            user=request.user,
            encounter=encounter,
            prompt_hash=_sha256(body["prompt"]),
            model=result.model,
            tool_call_count=result.tool_call_count,
            response_hash=_sha256(result.raw_response_text),
        )

        return Response(
            {
                "data": result.data,
                "meta": {
                    "model": result.model,
                    "tool_calls": result.tool_call_count,
                    "latency_ms": result.latency_ms,
                    "tokens": {
                        "input": result.input_tokens,
                        "output": result.output_tokens,
                    },
                },
            }
        )
