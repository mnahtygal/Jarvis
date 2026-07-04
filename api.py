from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, url_for
from flask_cors import CORS

from audio.listen import listen_command
from audio.speak import speak
from core.brain import think
from core.calibration import (
    apply_calibration_to_active_profile,
    compute_calibration_from_mat,
    get_active_camera_profile,
)
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
from skills.scan_mat_skill import analyze_scan_mat
from skills.vision_skill import DEFAULT_PROMPT, analyze_image

app = Flask(__name__)
CORS(app)

MAT_ANALYSIS_DIR = CAPTURE_DIR / "mat_analysis"


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
        mimetype="image/jpeg",
        conditional=True,
        max_age=0,
    )


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
    warning = None

    if not rectified_available:
        warning = "Rectified view is unavailable because the scan mat was not detected."

    return {
        "raw_image_url": _raw_artifact_url(snapshot_path),
        "annotated_image_url": _mat_artifact_url(mat_result.get("annotated_path")),
        "rectified_image_url": rectified_image_url,
        "scan_ok": bool(mat_result.get("ok")),
        "mat_detected": mat_detected,
        "corners": mat_result.get("mat", {}).get("corners"),
        "rectified_available": rectified_available,
        "warning": warning,
    }


@app.route("/api/camera/snapshot", methods=["POST"])
def api_camera_snapshot():
    return jsonify(capture_snapshot())


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

    capture_result = capture_snapshot()
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
    capture_result = capture_snapshot()
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
