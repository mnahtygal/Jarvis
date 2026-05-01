from flask import Flask, jsonify
from audio.listen import listen_command

app = Flask(__name__)

@app.route("/listen")
def listen():
    text = listen_command()
    return jsonify({"text": text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
