import hashlib
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care_ai.agent import (
    AgentError,
    AgentTimeoutError,
    OutputValidationError,
    RateLimitedError,
    ToolCallBudgetExceededError,
    UpstreamTimeoutError,
    run_agent,
)
from care_ai.api.serializers import AskRequestSerializer
from care_ai.models import AIRunAuditLog
from care_ai.permissions import authorize_encounter_read, resolve_encounter

logger = logging.getLogger("care_ai.views")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AskAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, encounter_external_id, *args, **kwargs):
        serializer = AskRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data

        encounter = resolve_encounter(encounter_external_id)
        authorize_encounter_read(request.user, encounter)

        try:
            result = run_agent(
                encounter=encounter,
                prompt=body["prompt"],
                response_schema=body.get("response_schema"),
                model=body.get("model") or None,
                max_tool_iterations=body.get("max_tool_iterations"),
            )
        except ToolCallBudgetExceededError as exc:
            logger.warning("agent run hit tool budget: %s", exc)
            return Response(
                {"error": "max_tool_iterations exceeded", "detail": str(exc)},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except (AgentTimeoutError, UpstreamTimeoutError) as exc:
            logger.warning("agent run timed out: %s", exc)
            return Response(
                {"error": "upstream timeout", "detail": str(exc)},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except RateLimitedError as exc:
            logger.warning("agent run rate-limited: %s", exc)
            return Response(
                {"error": "rate limited by openai", "detail": str(exc)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except OutputValidationError as exc:
            logger.exception("agent returned invalid output")
            return Response(
                {"error": "invalid_model_output", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except AgentError as exc:
            logger.exception("agent run failed")
            return Response(
                {"error": "agent run failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

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
                "output": result.output,
                "model": result.model,
                "usage": {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "total_tokens": result.input_tokens + result.output_tokens,
                },
                "tool_calls": result.tool_calls,
                "duration_ms": result.duration_ms,
            }
        )
