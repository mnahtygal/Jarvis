import importlib
import inspect
import json

import pytest


llama_module = importlib.import_module("skills.llama_cpp_skill")
proposal_module = importlib.import_module("core.developer_agent.repair_proposal")


class _Response:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [{
                "message": {"content": self._content},
                "finish_reason": "stop",
            }]
        }


def test_repair_inference_uses_fixed_grammar_and_deterministic_profile(monkeypatch):
    output = json.dumps({
        "proposal_type": "no_fix",
        "confidence": 0.25,
        "reason": "Evidence is insufficient",
    })
    captured: dict[str, object] = {}

    def post(url, *, json, timeout):
        captured.update({"url": url, "payload": json, "timeout": timeout})
        return _Response(output)

    monkeypatch.setattr(llama_module, "get_active_model_id", lambda: "test-model")
    monkeypatch.setattr(llama_module.requests, "post", post)

    result = llama_module.get_llama_cpp_repair_response("prompt", "system")

    assert result == output
    payload = captured["payload"]
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0.0
    assert payload["top_p"] == 0.1
    assert payload["top_k"] == 1
    assert payload["repeat_penalty"] == 1.0
    assert payload["seed"] == 0
    assert payload["max_tokens"] == 1200
    assert payload["stream"] is False
    assert payload["cache_prompt"] is False
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["grammar"] == llama_module._REPAIR_PROPOSAL_GBNF
    assert "response_format" not in payload
    assert captured["timeout"] == 240


def test_repair_schema_exactly_represents_three_existing_variants():
    schema = llama_module._repair_proposal_json_schema()
    variants = schema["oneOf"]

    assert len(variants) == 3
    expected = {
        "patch_file": {
            "proposal_type", "path", "old_text", "new_text", "confidence", "reason",
        },
        "write_file": {
            "proposal_type", "path", "content", "confidence", "reason",
        },
        "no_fix": {"proposal_type", "confidence", "reason"},
    }
    for variant in variants:
        proposal_type = variant["properties"]["proposal_type"]["const"]
        assert set(variant["properties"]) == expected[proposal_type]
        assert set(variant["required"]) == expected[proposal_type]
        assert variant["additionalProperties"] is False
        confidence = variant["properties"]["confidence"]
        assert confidence == {"type": "number", "minimum": 0.0, "maximum": 1.0}


def test_repair_inference_accepts_no_caller_grammar_or_schema():
    parameters = inspect.signature(
        llama_module.get_llama_cpp_repair_response
    ).parameters

    assert tuple(parameters) == ("prompt", "system_prompt")


@pytest.mark.parametrize(
    "data",
    [
        {
            "proposal_type": "patch_file",
            "path": "example.py",
            "old_text": "VALUE = 1\n",
            "new_text": "VALUE = \"two\"\\n\n",
            "confidence": 0.9,
            "reason": "Replace the exact value",
        },
        {
            "proposal_type": "write_file",
            "path": "test_example.py",
            "content": "def test_value():\n    assert VALUE == 2\n",
            "confidence": 0.8,
            "reason": "Add the missing focused test",
        },
        {
            "proposal_type": "no_fix",
            "confidence": 0.2,
            "reason": "Evidence is insufficient",
        },
    ],
)
def test_strict_parser_accepts_each_constrained_variant_and_escaped_strings(data):
    parsed = proposal_module._parse_model_output(json.dumps(data))

    assert parsed["proposal_type"] == data["proposal_type"]
    assert set(parsed) == set(data)


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        "```json\n{\"proposal_type\":\"no_fix\",\"confidence\":0.2,"
        "\"reason\":\"none\"}\n```",
        "Here is the proposal: {\"proposal_type\":\"no_fix\","
        "\"confidence\":0.2,\"reason\":\"none\"}",
        "{\"proposal_type\":\"no_fix\",\"confidence\":0.2,"
        "\"reason\":\"none\",\"extra\":true}",
    ],
)
def test_strict_parser_still_rejects_malformed_wrapped_or_extended_output(output):
    with pytest.raises(proposal_module._FormatError):
        proposal_module._parse_model_output(output)


def test_retry_bound_remains_one_initial_call_plus_one_correction():
    assert proposal_module.MAX_MODEL_CALLS == 2
    assert "No Markdown, prose, or text outside that object" in (
        proposal_module._prompt_for(
            proposal_module.RepairProposalRequest(
                "failed",
                "failure",
                ("example.py",),
                {"example.py": "VALUE = 1"},
            ),
            {"example.py": "VALUE = 1"},
            correction=True,
        )
    )
