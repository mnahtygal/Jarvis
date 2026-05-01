from flask import Flask, jsonify, request
from flask_cors import CORS

from audio.listen import listen_command
from audio.speak import speak
from core.brain import think

app = Flask(__name__)
CORS(app)


@app.route("/")
def home():
    return "Jarvis API is running"


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


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
        use_voice = bool(data.get("use_voice", True))

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
