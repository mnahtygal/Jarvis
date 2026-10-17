"""Conversational model output must not expose hidden reasoning markup."""

import importlib

import pytest


llama_module = importlib.import_module("skills.llama_cpp_skill")
ollama_module = importlib.import_module("skills.ollama_skill")


class _Response:
    def __init__(self, *, content="", reasoning="", response=""):
        self.content = content
        self.reasoning = reasoning
        self.response = response

    def raise_for_status(self):
        return None

    def json(self):
        if self.response:
            return {"response": self.response}
        return {
            "choices": [{
                "message": {
                    "content": self.content,
                    "reasoning_content": self.reasoning,
                },
            }],
        }


@pytest.mark.parametrize(("raw", "expected"), (
    ("<think>private</think>Visible", "Visible"),
    ("<think>outer <think>inner</think></think>Visible", "Visible"),
    ("<think>private", ""),
    ("</think>Visible", ""),
    ("Visible<think>private", "Visible"),
))
def test_conversational_thinking_sanitizer_never_surfaces_reasoning(raw, expected):
    assert llama_module.strip_thinking(raw) == expected


def test_general_llama_chat_never_uses_reasoning_content_as_answer(monkeypatch):
    monkeypatch.setattr(llama_module, "build_messages", lambda prompt: [])
    monkeypatch.setattr(llama_module, "get_active_model_id", lambda: "test-model")
    monkeypatch.setattr(
        llama_module.requests,
        "post",
        lambda *args, **kwargs: _Response(reasoning="private chain of thought"),
    )

    assert llama_module.get_llama_cpp_response("prompt") == ""


def test_ollama_conversational_fallback_sanitizes_thinking(monkeypatch):
    monkeypatch.setattr(ollama_module, "build_prompt", lambda prompt: prompt)
    monkeypatch.setattr(
        ollama_module.requests,
        "post",
        lambda *args, **kwargs: _Response(
            response="<think>private</think>Visible answer"
        ),
    )

    assert ollama_module.ask_ollama("prompt") == "Visible answer"


def test_structured_greenfield_output_preserves_literal_think_text(monkeypatch):
    output = '{"files":[{"path":"app.py","content":"VALUE = \'<think>\'"}]}'
    monkeypatch.setattr(llama_module, "get_active_model_id", lambda: "test-model")
    monkeypatch.setattr(
        llama_module.requests,
        "post",
        lambda *args, **kwargs: _Response(content=output),
    )

    result = llama_module.get_llama_cpp_greenfield_response(
        "prompt",
        "system",
        approved_paths=("app.py",),
    )

    assert result.content == output
    assert result.endpoint_status == "ok"


def test_structured_greenfield_removes_only_complete_leading_reasoning_envelope(
    monkeypatch,
):
    output = '{"files":[{"path":"app.py","content":"VALUE = \'<think>\'"}]}'
    wrapped = f"<think>private reasoning</think>\n{output}"
    monkeypatch.setattr(llama_module, "get_active_model_id", lambda: "test-model")
    monkeypatch.setattr(
        llama_module.requests,
        "post",
        lambda *args, **kwargs: _Response(content=wrapped),
    )

    result = llama_module.get_llama_cpp_greenfield_response(
        "prompt",
        "system",
        approved_paths=("app.py",),
    )

    assert result.content == output
    assert result.output_bytes == len(wrapped.encode("utf-8"))
