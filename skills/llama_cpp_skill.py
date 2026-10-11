# skills/llama_cpp_skill.py

import os
import re

import requests

from core.context import build_messages
from skills.model_runtime import get_active_model_id

LLAMA_CPP_URL = os.getenv(
    "LLAMA_CPP_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)


def strip_thinking(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def get_llama_cpp_response(prompt: str) -> str:
    payload = {
        "model": get_active_model_id(),
        "messages": build_messages(prompt),
        "temperature": 0.3,
        "max_tokens": 1200,
        "stream": False,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=180,
        )

        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        answer = message.get("content", "")

        if not answer:
            answer = message.get("reasoning_content", "")

        answer = strip_thinking(answer)

        return answer if answer else ""

    except Exception as error:
        print(f"[LLM] llama.cpp error: {error}")
        return ""


def get_llama_cpp_raw_response(
    prompt: str,
    system_prompt: str = "You are Jarvis, a local assistant. Follow the user's instructions exactly.",
    temperature: float = 0.2,
    max_tokens: int = 1800,
    log_errors: bool = True,
) -> str:
    payload = {
        "model": get_active_model_id(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=240,
        )

        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        answer = message.get("content", "")

        if not answer:
            answer = message.get("reasoning_content", "")

        answer = strip_thinking(answer)

        return answer if answer else ""

    except Exception as error:
        if log_errors:
            print(f"[LLM] llama.cpp raw error: {error}")
        return ""


def _repair_proposal_json_schema() -> dict:
    string = {"type": "string"}
    confidence = {"type": "number", "minimum": 0.0, "maximum": 1.0}
    reason = {"type": "string"}
    variants = (
        {
            "type": "object",
            "properties": {
                "proposal_type": {"const": "patch_file"},
                "path": string,
                "old_text": string,
                "new_text": string,
                "confidence": confidence,
                "reason": reason,
            },
            "required": [
                "proposal_type",
                "path",
                "old_text",
                "new_text",
                "confidence",
                "reason",
            ],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "proposal_type": {"const": "write_file"},
                "path": string,
                "content": string,
                "confidence": confidence,
                "reason": reason,
            },
            "required": [
                "proposal_type",
                "path",
                "content",
                "confidence",
                "reason",
            ],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "proposal_type": {"const": "no_fix"},
                "confidence": confidence,
                "reason": reason,
            },
            "required": ["proposal_type", "confidence", "reason"],
            "additionalProperties": False,
        },
    )
    return {"oneOf": list(variants)}


_REPAIR_PROPOSAL_GBNF = "\n".join((
    r'root ::= patch | write | no-fix',
    r'patch ::= "{" ws patch-type "," ws path "," ws old-text "," ws '
    r'new-text "," ws confidence "," ws reason "}" ws',
    r'write ::= "{" ws write-type "," ws path "," ws content "," ws '
    r'confidence "," ws reason "}" ws',
    r'no-fix ::= "{" ws no-fix-type "," ws confidence "," ws reason "}" ws',
    r'patch-type ::= "\"proposal_type\"" ws ":" ws "\"patch_file\"" ws',
    r'write-type ::= "\"proposal_type\"" ws ":" ws "\"write_file\"" ws',
    r'no-fix-type ::= "\"proposal_type\"" ws ":" ws "\"no_fix\"" ws',
    r'path ::= "\"path\"" ws ":" ws string',
    r'old-text ::= "\"old_text\"" ws ":" ws string',
    r'new-text ::= "\"new_text\"" ws ":" ws string',
    r'content ::= "\"content\"" ws ":" ws string',
    r'confidence ::= "\"confidence\"" ws ":" ws confidence-number ws',
    r'reason ::= "\"reason\"" ws ":" ws string',
    r'confidence-number ::= "0" ("." [0-9]+)? | "1" ("." "0"+)?',
    r'string ::= "\"" char* "\"" ws',
    r'char ::= [^"\\\x7F\x00-\x1F] | "\\" '
    r'(["\\/bfnrt] | "u" [0-9a-fA-F]{4})',
    r'ws ::= [ \t\n\r]*',
))


def get_llama_cpp_repair_response(prompt: str, system_prompt: str) -> str:
    """Request one fixed-schema Developer Agent repair proposal."""

    payload = {
        "model": get_active_model_id(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "top_p": 0.1,
        "top_k": 1,
        "repeat_penalty": 1.0,
        "seed": 0,
        "max_tokens": 1200,
        "stream": False,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "grammar": _REPAIR_PROPOSAL_GBNF,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=240,
        )
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        answer = message.get("content", "")
        if not answer:
            answer = message.get("reasoning_content", "")
        answer = strip_thinking(answer)
        return answer if answer else ""
    except Exception:
        return ""


def ask_llama_cpp(prompt: str) -> str:
    return get_llama_cpp_response(prompt)


def ask_local_llm(prompt: str) -> str:
    return get_llama_cpp_response(prompt)


def get_llm_response(prompt: str) -> str:
    return get_llama_cpp_response(prompt)
