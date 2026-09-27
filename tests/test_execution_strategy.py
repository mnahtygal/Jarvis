from core.execution_strategy import (
    ExecutionStrategy,
    determine_execution_strategy,
)
from core.request_classifier import classify_request
from core.result_evaluator import evaluate_response


def test_execution_strategy_mappings():
    cases = {
        "what is my wife's name": ExecutionStrategy.MEMORY,
        "remember that my favorite color is blue": ExecutionStrategy.MEMORY,
        "what did I tell you about Jarvis memory": ExecutionStrategy.SEMANTIC_MEMORY,
        "what is PostgreSQL": ExecutionStrategy.LLM,
        "tell me more": ExecutionStrategy.LLM,
        "brain status": ExecutionStrategy.SYSTEM,
        "which camera is active": ExecutionStrategy.SYSTEM,
        "capture a snapshot": ExecutionStrategy.CAMERA_VISION,
        "help": ExecutionStrategy.DETERMINISTIC,
        "make something interesting": ExecutionStrategy.LLM,
    }

    for command, expected in cases.items():
        assert determine_execution_strategy(classify_request(command)) is expected


def test_response_evaluation():
    assert evaluate_response("Normal Jarvis response.") == evaluate_response("Normal Jarvis response.")
    assert evaluate_response("Normal Jarvis response.").quality == "good"
    assert evaluate_response("Normal Jarvis response.").success is True

    empty = evaluate_response("   ")
    assert empty.success is False
    assert empty.quality == "failed"
    assert empty.reason == "empty response"

    degraded = evaluate_response("Sorry Marty, both local brain paths failed. Error: unavailable")
    assert degraded.success is False
    assert degraded.quality == "degraded"
    assert degraded.reason == "local model fallback failure"


def test_strategy_mapping_is_side_effect_free():
    classification = classify_request("what is PostgreSQL")

    assert determine_execution_strategy(classification) is ExecutionStrategy.LLM
