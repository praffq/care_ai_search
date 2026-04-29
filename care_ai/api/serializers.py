from rest_framework import serializers

from care_ai.settings import plugin_settings


class RunAIRequestSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    prompt = serializers.CharField()
    model = serializers.CharField(required=False, allow_blank=True, default="")
    output_format = serializers.DictField()
    max_tool_calls = serializers.IntegerField(required=False, min_value=1, max_value=20)

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
