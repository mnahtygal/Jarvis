from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, url_for
from flask_cors import CORS

from audio.listen import listen_command
from core.camera_roles import DEFAULT_CAMERA_ROLE, get_camera_roles_status, set_active_camera_role
from audio.speak import speak
from core.brain import think
from core.calibration import (
    apply_calibration_to_active_profile,
    compute_calibration_from_mat,
    get_active_camera_profile,
)
from core.measurement import measure_object_bbox_from_image
from skills.architecture_status_skill import get_architecture_status
from skills.calibration_skill import get_calibration_status
from skills.camera_diagnostics_skill import get_camera_diagnostics_status
from skills.camera_skill import CAPTURE_DIR, capture_snapshot
from skills.dashboard_status_skill import (
    get_brain_dashboard_status,
    get_dashboard_status,
    get_martybench_dashboard_status,
    get_memory_dashboard_status,
    get_model_dashboard_status,
)
from skills.device_status_skill import get_device_dashboard_status
from skills.measurement_skill import get_measurement_status
from skills.scan_mat_skill import analyze_scan_mat
from skills.vision_skill import DEFAULT_PROMPT, analyze_image

app = Flask(__name__)
CORS(app)

PROJECT_ROOT = Path(__file__).resolve().parent
MAT_ANALYSIS_DIR = CAPTURE_DIR / "mat_analysis"
GRAPHIFY_OUTPUT_DIR = PROJECT_ROOT / "runtime" / "graphify" / "graphify-out"


def _latest_snapshot_path() -> Path | None:
    if not CAPTURE_DIR.exists():
        return None

    snapshots = [
        path
        for path in CAPTURE_DIR.glob("snapshot_*.jpg")
        if path.is_file()
    ]
    if not snapshots:
        return None

    return max(snapshots, key=lambda path: path.stat().st_mtime)


def _resolve_artifact_path(base_dir: Path, artifact_name: str) -> Path | None:
    base_path = base_dir.resolve()
    artifact_path = (base_path / artifact_name).resolve()

    try:
        artifact_path.relative_to(base_path)
    except ValueError:
        return None

    if not artifact_path.is_file():
        return None

    return artifact_path


def _serve_artifact(base_dir: Path, artifact_name: str):
    artifact_path = _resolve_artifact_path(base_dir, artifact_name)
    if artifact_path is None:
        abort(404)

    return send_file(
        artifact_path,
        conditional=True,
        max_age=0,
    )


def _resolve_measurement_image_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None

    requested_path = Path(raw_path)
    if not requested_path.is_absolute():
        requested_path = PROJECT_ROOT / requested_path

    try:
        resolved_path = requested_path.resolve()
    except Exception:
        return None

    try:
        resolved_path.relative_to(MAT_ANALYSIS_DIR.resolve())
    except ValueError:
        return None

    if not resolved_path.name.endswith("_mat_rectified.jpg"):
        return None
    return resolved_path if resolved_path.is_file() else None


def _raw_artifact_url(snapshot_path: Path) -> str:
    return url_for(
        "api_camera_artifact",
        artifact_name=snapshot_path.name,
        _external=True,
    )


def _mat_artifact_url(artifact_path: str | None) -> str | None:
    if not artifact_path:
        return None

    path = Path(artifact_path)
    if _resolve_artifact_path(MAT_ANALYSIS_DIR, path.name) is None:
        return None

    return url_for(
        "api_scan_mat_artifact",
        artifact_name=path.name,
        _external=True,
    )


def _scan_mat_metadata(snapshot_path: Path, mat_result: dict) -> dict:
    rectified_image_url = _mat_artifact_url(mat_result.get("rectified_path"))
    rectified_available = bool(rectified_image_url)
    mat_detected = bool(mat_result.get("mat_detected"))
    diagnostics = mat_result.get("diagnostics") or {}
    failure_reason = diagnostics.get("failure_reason")
    warning = None

    if not rectified_available:
        if failure_reason:
            warning = f"Rectified view is unavailable: {failure_reason}."
        else:
            warning = "Rectified view is unavailable because the scan mat was not detected."

    return {
        "raw_image_url": _raw_artifact_url(snapshot_path),
        "annotated_image_url": _mat_artifact_url(mat_result.get("annotated_path")),
        "rectified_image_url": rectified_image_url,
        "scan_ok": bool(mat_result.get("ok")),
        "mat_detected": mat_detected,
        "corners": mat_result.get("mat", {}).get("corners"),
        "rectified_available": rectified_available,
        "failure_reason": failure_reason,
        "warning": warning,
    }


@app.route("/api/camera/snapshot", methods=["POST"])
def api_camera_snapshot():
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    device = data.get("device")
    result = capture_snapshot(device=device, role=role)
    return jsonify(result), 200 if result.get("ok") else 503


@app.route("/api/cameras", methods=["GET"])
def api_cameras():
    return jsonify(get_camera_roles_status())


@app.route("/api/camera/active", methods=["GET"])
def api_camera_active():
    status = get_camera_roles_status()
    return jsonify({
        "ok": True,
        "active_role": status.get("active_role"),
        "active_camera": status.get("active_camera"),
    })


@app.route("/api/camera/active", methods=["POST"])
def api_camera_switch_active():
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip()
    if not role:
        return jsonify({
            "ok": False,
            "error": "role is required.",
        }), 400

    try:
        status = set_active_camera_role(role)
    except ValueError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 409
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500

    return jsonify(status)


@app.route("/api/camera/latest", methods=["GET"])
def api_camera_latest():
    snapshot_path = _latest_snapshot_path()
    if snapshot_path is None:
        return jsonify({
            "ok": False,
            "error": "No camera snapshot is available yet."
        }), 404

    return send_file(
        snapshot_path,
        mimetype="image/jpeg",
        conditional=True,
        max_age=0,
    )


@app.route("/api/vision/artifacts/raw/<path:artifact_name>", methods=["GET"])
def api_camera_artifact(artifact_name: str):
    return _serve_artifact(CAPTURE_DIR, artifact_name)


@app.route("/api/vision/artifacts/mat-analysis/<path:artifact_name>", methods=["GET"])
def api_scan_mat_artifact(artifact_name: str):
    return _serve_artifact(MAT_ANALYSIS_DIR, artifact_name)


@app.route("/api/architecture/tree", methods=["GET"])
def api_architecture_tree():
    return _serve_artifact(GRAPHIFY_OUTPUT_DIR, "JARVIS_TREE.html")


@app.route("/api/architecture/callflow", methods=["GET"])
def api_architecture_callflow():
    return _serve_artifact(GRAPHIFY_OUTPUT_DIR, "graphify-callflow.html")


@app.route("/api/camera/analyze", methods=["POST"])
def api_camera_analyze():
    snapshot_path = _latest_snapshot_path()
    if snapshot_path is None:
        return jsonify({
            "ok": False,
            "error": "No camera snapshot is available yet."
        }), 404

    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or DEFAULT_PROMPT).strip()
    result = analyze_image(snapshot_path, prompt=prompt)
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.route("/api/camera/capture-analyze", methods=["POST"])
def api_camera_capture_analyze():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or DEFAULT_PROMPT).strip()
    mode = (data.get("mode") or "general").strip()
    role = (data.get("role") or "").strip() or None
    device = (data.get("device") or "").strip() or None

    capture_result = capture_snapshot(device=device, role=role)
    if not capture_result.get("ok"):
        return jsonify({
            "ok": False,
            "mode": mode,
            "capture": capture_result,
            "error": capture_result.get("error", "Camera capture failed."),
        }), 503

    snapshot_path = Path(capture_result.get("file_path", ""))
    if not snapshot_path.exists():
        latest_snapshot = _latest_snapshot_path()
        if latest_snapshot is None:
            return jsonify({
                "ok": False,
                "mode": mode,
                "capture": capture_result,
                "error": "Camera capture succeeded but no snapshot file was found.",
            }), 503
        snapshot_path = latest_snapshot

    analysis_result = analyze_image(snapshot_path, prompt=prompt)
    if not analysis_result.get("ok"):
        return jsonify({
            "ok": False,
            "mode": mode,
            "capture": capture_result,
            "analysis": analysis_result,
            "error": analysis_result.get("error", "Vision analysis failed."),
        }), 503

    return jsonify({
        "ok": True,
        "mode": mode,
        "capture": capture_result,
        "analysis": analysis_result,
        "description": analysis_result.get("description", ""),
        "image_name": analysis_result.get("image_name", snapshot_path.name),
        "model": analysis_result.get("model"),
    })


@app.route("/api/vision/scan-mat", methods=["POST"])
def api_vision_scan_mat():
    snapshot_path = _latest_snapshot_path()
    if snapshot_path is None:
        return jsonify({
            "ok": False,
            "error": "No camera snapshot is available yet."
        }), 404

    mat_result = analyze_scan_mat(snapshot_path)
    return jsonify({
        **mat_result,
        **_scan_mat_metadata(snapshot_path, mat_result),
    })


@app.route("/api/vision/capture-scan-mat", methods=["POST"])
def api_vision_capture_scan_mat():
    capture_result = capture_snapshot(role=DEFAULT_CAMERA_ROLE)
    if not capture_result.get("ok"):
        return jsonify({
            "ok": False,
            "capture": capture_result,
            "error": capture_result.get("error", "Camera capture failed."),
        }), 503

    snapshot_path = Path(capture_result.get("file_path", ""))
    if not snapshot_path.exists():
        latest_snapshot = _latest_snapshot_path()
        if latest_snapshot is None:
            return jsonify({
                "ok": False,
                "capture": capture_result,
                "error": "Camera capture succeeded but no snapshot file was found.",
            }), 503
        snapshot_path = latest_snapshot

    mat_result = analyze_scan_mat(snapshot_path)
    scan_metadata = _scan_mat_metadata(snapshot_path, mat_result)
    status_code = 200 if mat_result.get("ok") else 422
    return jsonify({
        "ok": bool(mat_result.get("ok")),
        "capture": capture_result,
        "mat_analysis": mat_result,
        "diagnostics": mat_result.get("diagnostics"),
        "image_name": snapshot_path.name,
        **scan_metadata,
    }), status_code


@app.route("/")
def home():
    return "Jarvis API is running"


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/status/dashboard", methods=["GET"])
def api_status_dashboard():
    return jsonify(get_dashboard_status())


@app.route("/api/status/architecture", methods=["GET"])
def api_status_architecture():
    return jsonify(get_architecture_status())


@app.route("/api/status/brain", methods=["GET"])
def api_status_brain():
    return jsonify(get_brain_dashboard_status())


@app.route("/api/status/model", methods=["GET"])
def api_status_model():
    return jsonify(get_model_dashboard_status())


@app.route("/api/status/memory", methods=["GET"])
def api_status_memory():
    return jsonify(get_memory_dashboard_status())


@app.route("/api/status/martybench", methods=["GET"])
def api_status_martybench():
    return jsonify(get_martybench_dashboard_status())


@app.route("/api/status/devices", methods=["GET"])
def api_status_devices():
    return jsonify(get_device_dashboard_status())


@app.route("/api/status/camera-diagnostics", methods=["GET"])
def api_status_camera_diagnostics():
    return jsonify(get_camera_diagnostics_status())


@app.route("/api/status/calibration", methods=["GET"])
def api_status_calibration():
    return jsonify(get_calibration_status())


@app.route("/api/status/measurement", methods=["GET"])
def api_status_measurement():
    return jsonify(get_measurement_status())


@app.route("/api/measurement/analyze", methods=["POST"])
def api_measurement_analyze():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "JSON body is required.",
        }), 400

    image_path = data.get("image_path")
    if not isinstance(image_path, str) or not image_path.strip():
        return jsonify({
            "ok": False,
            "error": "image_path is required.",
        }), 400

    resolved_path = _resolve_measurement_image_path(image_path.strip())
    if resolved_path is None:
        return jsonify({
            "ok": False,
            "error": "image_path must point to an existing Jarvis runtime/camera artifact or /tmp file.",
        }), 400

    result = measure_object_bbox_from_image(str(resolved_path))
    measurement = result.get("measurement") or {}
    artifacts = measurement.get("artifacts") or {}
    if artifacts:
        artifacts["mask_url"] = _mat_artifact_url(artifacts.get("mask_path"))
        artifacts["overlay_url"] = _mat_artifact_url(artifacts.get("overlay_path"))

    if result.get("ok"):
        status_code = 200
    else:
        failure_reason = (result.get("diagnostics") or {}).get("failure_reason")
        status_code = 422 if failure_reason in {
            "calibration_not_ready",
            "no_object_found",
            "ambiguous_object_candidates",
            "object_touching_image_boundary",
        } else 500
    return jsonify(result), status_code


@app.route("/api/calibration/profile", methods=["GET"])
def api_calibration_profile():
    try:
        return jsonify({
            "ok": True,
            "profile": get_active_camera_profile(),
        })
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


@app.route("/api/calibration/apply", methods=["POST"])
def api_calibration_apply():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "JSON body is required.",
        }), 400

    if "corners" not in data:
        return jsonify({
            "ok": False,
            "error": "corners is required.",
        }), 400

    if "known_width_mm" not in data:
        return jsonify({
            "ok": False,
            "error": "known_width_mm is required.",
        }), 400

    if "known_height_mm" not in data:
        return jsonify({
            "ok": False,
            "error": "known_height_mm is required.",
        }), 400

    try:
        calibration = compute_calibration_from_mat(
            corners=data["corners"],
            known_width_mm=data["known_width_mm"],
            known_height_mm=data["known_height_mm"],
            image_width_px=data.get("image_width_px"),
            image_height_px=data.get("image_height_px"),
        )
        updated_profile = apply_calibration_to_active_profile(calibration)
    except ValueError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500

    return jsonify({
        "ok": True,
        "profile": updated_profile,
        "calibration": calibration,
    })


@app.route("/listen", methods=["GET"])
def listen():
    heard = listen_command()
    return jsonify({"text": heard})


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(silent=True) or {}
        use_voice = bool(data.get("use_voice", True))

        heard = listen_command()

        if not heard:
            return jsonify({
                "heard": "",
                "response": "I didn't catch that. Please try again."
            })

        response = think(heard)

        if use_voice and response:
            speak(response)

        return jsonify({
            "heard": heard,
            "response": response
        })

    except Exception as e:
        print(f"/ask error: {e}")
        return jsonify({
            "heard": "",
            "response": "Something went wrong while processing your request."
        }), 500


@app.route("/text", methods=["POST"])
def text():
    try:
        data = request.get_json(silent=True) or {}
        command = (data.get("command") or "").strip()
        use_voice = bool(data.get("use_voice", False))

        if not command:
            return jsonify({
                "heard": "",
                "response": "Please type a command first."
            }), 400

        response = think(command)

        if use_voice and response:
            speak(response)

        return jsonify({
            "heard": command,
            "response": response
        })

    except Exception as e:
        print(f"/text error: {e}")
        return jsonify({
            "heard": "",
            "response": "Something went wrong while handling typed input."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
