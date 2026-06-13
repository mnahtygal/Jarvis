from flask import Flask, jsonify, request
from flask_cors import CORS
from skills.camera_skill import capture_snapshot
from audio.listen import listen_command
from audio.speak import speak
from core.brain import think
from skills.dashboard_status_skill import (
    get_brain_dashboard_status,
    get_dashboard_status,
    get_martybench_dashboard_status,
    get_memory_dashboard_status,
    get_model_dashboard_status,
)
from skills.device_status_skill import get_device_dashboard_status

app = Flask(__name__)
CORS(app)


@app.route("/api/camera/snapshot", methods=["POST"])
def api_camera_snapshot():
    return jsonify(capture_snapshot())

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
