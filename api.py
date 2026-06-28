from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from audio.listen import listen_command
from audio.speak import speak
from core.brain import think
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

    return jsonify(analyze_scan_mat(snapshot_path))


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
    status_code = 200 if mat_result.get("ok") else 422
    return jsonify({
        "ok": bool(mat_result.get("ok")),
        "capture": capture_result,
        "mat_analysis": mat_result,
        "image_name": snapshot_path.name,
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
