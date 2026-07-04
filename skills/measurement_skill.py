from __future__ import annotations

from typing import Any, Dict

from core.measurement import MEASUREMENT_METHOD, get_active_calibration


def get_measurement_status() -> Dict[str, Any]:
    calibration = get_active_calibration()
    ready = bool(calibration.get("ready"))

    return {
        "ready": ready,
        "measurement_engine_ready": ready,
        "active_profile_id": calibration.get("profile_id"),
        "active_profile_name": calibration.get("profile_name"),
        "calibration_ready": ready,
        "calibration_confidence": calibration.get("confidence"),
        "supported_methods": [MEASUREMENT_METHOD],
        "error": None if ready else calibration.get("error"),
    }
