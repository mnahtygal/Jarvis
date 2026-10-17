"""UI transport compatibility tests for the existing synchronous chat routes."""

from unittest.mock import Mock

import api


def test_text_keeps_ui_compatible_shape_and_routes_through_think(monkeypatch):
    think = Mock(return_value="line one\nline two")
    monkeypatch.setattr(api, "think", think)
    client = api.app.test_client()

    response = client.post(
        "/text",
        json={"command": "  Read core/brain.py  ", "use_voice": False},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "heard": "Read core/brain.py",
        "response": "line one\nline two",
    }
    think.assert_called_once_with("Read core/brain.py")


def test_approval_followups_remain_ordinary_text_requests(monkeypatch):
    think = Mock(side_effect=(
        "Confirmation required. Reply exactly 'approve'.",
        "File written successfully",
        "No pending action.",
    ))
    monkeypatch.setattr(api, "think", think)
    client = api.app.test_client()

    proposed = client.post("/text", json={"command": "Create demo.py with hello"})
    approved = client.post("/text", json={"command": "approve"})
    no_pending = client.post("/text", json={"command": "approve"})

    assert proposed.get_json()["response"].startswith("Confirmation required")
    assert approved.get_json()["response"] == "File written successfully"
    assert no_pending.get_json()["response"] == "No pending action."
    assert [call.args[0] for call in think.call_args_list] == [
        "Create demo.py with hello",
        "approve",
        "approve",
    ]


def test_cancellation_routes_through_think_as_ordinary_text(monkeypatch):
    think = Mock(side_effect=(
        "Confirmation required. Reply exactly 'approve' or 'cancel'.",
        "Pending action cancelled.",
    ))
    monkeypatch.setattr(api, "think", think)
    client = api.app.test_client()

    proposed = client.post("/text", json={"command": "Create demo.py with hello"})
    cancelled = client.post("/text", json={"command": "cancel"})

    assert proposed.status_code == cancelled.status_code == 200
    assert "confirmation" in proposed.get_json()["response"].casefold()
    assert "cancelled" in cancelled.get_json()["response"].casefold()
    assert [call.args[0] for call in think.call_args_list] == [
        "Create demo.py with hello",
        "cancel",
    ]


def test_bounded_session_confirmation_and_approval_route_through_think(monkeypatch):
    think = Mock(side_effect=(
        "Confirmation required for developer.bounded_session.",
        "Bounded developer session passed. Verification runs: 2.",
    ))
    monkeypatch.setattr(api, "think", think)
    client = api.app.test_client()

    command = "Fix calculator.py until test_calculator.py passes"
    proposed = client.post("/text", json={"command": command})
    approved = client.post("/text", json={"command": "approve"})

    assert proposed.status_code == approved.status_code == 200
    assert "confirmation" in proposed.get_json()["response"].casefold()
    assert "session passed" in approved.get_json()["response"]
    assert [call.args[0] for call in think.call_args_list] == [command, "approve"]


def test_text_backend_failure_returns_safe_ui_compatible_json(monkeypatch):
    monkeypatch.setattr(api, "think", Mock(side_effect=RuntimeError("private detail")))
    client = api.app.test_client()

    response = client.post("/text", json={"command": "Hello"})

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json() == {
        "heard": "",
        "response": "Something went wrong while handling typed input.",
    }
    assert "private detail" not in response.get_data(as_text=True)
