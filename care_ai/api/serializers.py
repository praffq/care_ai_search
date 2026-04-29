from rest_framework import serializers

from care_ai.output_schema import InvalidResponseSchema, validate_schema
from care_ai.settings import plugin_settings


class AskRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    model = serializers.CharField(required=False, allow_blank=True, default="")
    response_schema = serializers.JSONField(required=False, allow_null=True)
    max_tool_iterations = serializers.IntegerField(
        required=False, min_value=1, max_value=25
    )

    def validate_prompt(self, value: str) -> str:
        cap = plugin_settings.AI_PROMPT_MAX_CHARS
        if len(value) > cap:
            raise serializers.ValidationError(f"prompt exceeds {cap} characters")
        return value

    def validate_model(self, value: str) -> str:
        if not value:
            return value
        allowed = plugin_settings.AI_ALLOWED_MODELS
        if value not in allowed:
            raise serializers.ValidationError(f"model must be one of {sorted(allowed)}")
        return value

    def validate_response_schema(self, value):
        if value in (None, {}):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("response_schema must be a JSON object")
        try:
            validate_schema(value)
        except InvalidResponseSchema as exc:
            raise serializers.ValidationError(str(exc))
        return value
