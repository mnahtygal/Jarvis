from experiments.grounded_sam.config import DetectorGuardrails
from experiments.grounded_sam.detector import (
    evaluate_candidate,
    select_best_candidate,
)


GUARDRAILS = DetectorGuardrails()


def candidate(box, score=0.5):
    return evaluate_candidate(
        box=box,
        score=score,
        prompt="a small blue circuit board.",
        image_width=1920,
        image_height=1080,
        guardrails=GUARDRAILS,
    )


def test_accepts_verified_board_box():
    result = candidate(
        [729.88, 259.68, 1018.22, 412.20],
        0.543,
    )

    assert result.accepted is True
    assert result.touches_boundary is False
    assert 0.02 < result.area_ratio < 0.022
    assert result.rejection_reasons == ()


def test_rejects_verified_full_frame_false_detection():
    result = candidate(
        [4.55, 4.21, 1913.55, 1023.79],
        0.4719,
    )

    assert result.accepted is False
    assert result.touches_boundary is True
    assert "area_too_large" in result.rejection_reasons
    assert "touches_image_boundary" in result.rejection_reasons


def test_rejects_tiny_candidate():
    result = candidate([500, 500, 501, 501])

    assert result.accepted is False
    assert "area_too_small" in result.rejection_reasons


def test_rejects_invalid_geometry():
    result = candidate([500, 500, 400, 400])

    assert result.accepted is False
    assert "invalid_box_geometry" in result.rejection_reasons


def test_selects_highest_scoring_accepted_candidate():
    lower = candidate([700, 250, 1000, 410], 0.45)
    higher = candidate([710, 255, 1010, 415], 0.75)
    rejected = candidate([0, 0, 1919, 1079], 0.99)

    selected = select_best_candidate(
        [lower, rejected, higher]
    )

    assert selected == higher


def test_returns_none_when_every_candidate_is_rejected():
    first = candidate([0, 0, 1919, 1079], 0.99)
    second = candidate([4, 4, 1910, 1020], 0.85)

    assert select_best_candidate([first, second]) is None
