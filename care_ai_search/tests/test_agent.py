"""Tests for the agent loop with a mocked OpenAI client.

Lives inside the plugin so it ships with the package and runs under
`make test path=care_ai_search` from the host CARE repo.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from care_ai_search.agent import (
    AgentError,
    OutputValidationError,
    ToolCallBudgetExceededError,
    run_agent,
)


def _completion(
    content=None, tool_calls=None, *, prompt_tokens=10, completion_tokens=5
):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )


def _tool_call(call_id, name, arguments="{}"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


SIMPLE_OUTPUT_FORMAT = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}


def _fake_encounter():
    patient = SimpleNamespace(
        external_id="00000000-0000-0000-0000-000000000111",
        date_of_birth=None,
        year_of_birth=1990,
        gender="male",
        blood_group="O+",
        deceased_datetime=None,
        pk=1,
    )
    return SimpleNamespace(
        external_id="00000000-0000-0000-0000-000000000222",
        patient=patient,
        patient_id=1,
        pk=1,
    )


def _patched_settings(api_key="sk-test"):
    return patch(
        "care_ai_search.agent.plugin_settings",
        SimpleNamespace(
            AI_API_KEY=api_key,
            AI_BASE_URL="https://api.openai.test/v1",
            AI_TIMEOUT_SECONDS=30,
            AI_MAX_TOOL_CALLS=5,
            AI_DEFAULT_MODEL="gpt-test",
            AI_ALLOWED_MODELS=["gpt-test"],
            AI_PROMPT_MAX_CHARS=2000,
        ),
    )


class AgentLoopTests(SimpleTestCase):
    def setUp(self):
        p = _patched_settings()
        self.addCleanup(p.stop)
        p.start()

    @patch("care_ai_search.agent.OpenAI")
    def test_returns_validated_data_when_model_emits_no_tool_calls(self, openai_cls):
        openai_cls.return_value.chat.completions.create.return_value = _completion(
            content='{"summary": "patient stable"}'
        )

        result = run_agent(
            encounter=_fake_encounter(),
            prompt="Summarise.",
            output_format=SIMPLE_OUTPUT_FORMAT,
        )

        self.assertEqual(result.data, {"summary": "patient stable"})
        self.assertEqual(result.tool_call_count, 0)
        self.assertGreater(result.input_tokens, 0)

    @patch("care_ai_search.agent.OpenAI")
    def test_dispatches_tool_call_then_returns_final_answer(self, openai_cls):
        client = openai_cls.return_value
        client.chat.completions.create.side_effect = [
            _completion(tool_calls=[_tool_call("c1", "get_patient_demographics")]),
            _completion(content='{"summary": "30y male, O+"}'),
        ]

        with patch("care_ai_search.agent.TOOLS") as tools_mock:
            tool_obj = MagicMock()
            tool_obj.run.return_value = {"age_years": 30}
            tool_obj.openai_schema.return_value = {
                "type": "function",
                "function": {
                    "name": "get_patient_demographics",
                    "description": "x",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            }
            tools_mock.values.return_value = [tool_obj]
            tools_mock.get.return_value = tool_obj

            result = run_agent(
                encounter=_fake_encounter(),
                prompt="brief",
                output_format=SIMPLE_OUTPUT_FORMAT,
            )

        self.assertEqual(result.tool_call_count, 1)
        tool_obj.run.assert_called_once()
        called_kwargs = tool_obj.run.call_args.kwargs
        self.assertIn("encounter", called_kwargs)

    @patch("care_ai_search.agent.OpenAI")
    def test_tool_call_budget_is_enforced(self, openai_cls):
        infinite = _completion(tool_calls=[_tool_call("c", "get_patient_demographics")])
        openai_cls.return_value.chat.completions.create.return_value = infinite

        with patch("care_ai_search.agent.TOOLS") as tools_mock:
            tool_obj = MagicMock()
            tool_obj.run.return_value = {"ok": True}
            tool_obj.openai_schema.return_value = {
                "type": "function",
                "function": {
                    "name": "get_patient_demographics",
                    "description": "x",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            }
            tools_mock.values.return_value = [tool_obj]
            tools_mock.get.return_value = tool_obj

            with self.assertRaises(ToolCallBudgetExceededError):
                run_agent(
                    encounter=_fake_encounter(),
                    prompt="x",
                    output_format=SIMPLE_OUTPUT_FORMAT,
                    max_tool_calls=2,
                )

    @patch("care_ai_search.agent.OpenAI")
    def test_invalid_model_output_is_rejected(self, openai_cls):
        openai_cls.return_value.chat.completions.create.return_value = _completion(
            content='{"unexpected": 1}'
        )
        with self.assertRaises(OutputValidationError):
            run_agent(
                encounter=_fake_encounter(),
                prompt="x",
                output_format=SIMPLE_OUTPUT_FORMAT,
            )

    def test_missing_api_key_raises_agent_error(self):
        with _patched_settings(api_key=""), self.assertRaises(AgentError):
            run_agent(
                encounter=_fake_encounter(),
                prompt="x",
                output_format=SIMPLE_OUTPUT_FORMAT,
            )

    def test_malformed_output_format_fails_fast(self):
        with self.assertRaises(OutputValidationError):
            run_agent(
                encounter=_fake_encounter(),
                prompt="x",
                output_format={"type": "array", "items": {"type": "string"}},
            )

    @patch("care_ai_search.agent.OpenAI")
    def test_json_schema_is_wrapped_for_openai(self, openai_cls):
        openai_cls.return_value.chat.completions.create.return_value = _completion(
            content='{"encounter_id": "e1", "allergies": ["peanut"]}'
        )

        schema = {
            "type": "object",
            "properties": {
                "encounter_id": {"type": "string"},
                "allergies": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["encounter_id", "allergies"],
        }
        result = run_agent(
            encounter=_fake_encounter(),
            prompt="x",
            output_format=schema,
        )

        self.assertEqual(result.data, {"encounter_id": "e1", "allergies": ["peanut"]})
        sent = openai_cls.return_value.chat.completions.create.call_args.kwargs[
            "response_format"
        ]
        self.assertEqual(sent["type"], "json_schema")
        self.assertEqual(sent["json_schema"]["schema"], schema)
