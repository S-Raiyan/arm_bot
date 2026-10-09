import os
import json
import time
import threading
import requests
import numpy as np

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from vosk import Model, KaldiRecognizer
import pyaudio


# ============================================================
# CONFIGURATION
# ============================================================

app = Flask(__name__)
CORS(app)

ROBOT_IP = "192.168.4.1"
API_URL = f"http://{ROBOT_IP}/js"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model")

SAMPLE_RATE = 16000
FRAMES_PER_BUFFER = 8000

latest_status = "System online. Waiting for voice commands."
current_mic_volume = 0
last_spoken_sentence = "None"

# Protect normal robot gestures from running simultaneously.
robot_lock = threading.Lock()

# STOP state: cancels application-level gesture sequences.
stop_event = threading.Event()

# Serializes HTTP requests to the robot.
http_lock = threading.Lock()


# ============================================================
# ROBOT COMMUNICATION
# ============================================================

def send_to_robot(payload):
    """
    Send a JSON command to the robot.

    A successful HTTP response confirms that the request was
    accepted at the HTTP level; it does not necessarily confirm
    that the robot physically completed the movement.
    """
    global latest_status

    try:
        with http_lock:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=3
            )

        response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return {"response": response.text}

    except requests.exceptions.RequestException as exc:
        latest_status = (
            "Robot connection failed. Check Wi-Fi, "
            "robot IP, and robot HTTP server."
        )
        print(f"Robot communication error: {exc}")
        return None


def move_arm(
    base=0,
    shoulder=45,
    elbow=45,
    wrist=90,
    speed=25,
    acceleration=15
):
    """Send a joint-angle command using the existing T=122 format."""
    if stop_event.is_set():
        return None

    return send_to_robot({
        "T": 122,
        "b": base,
        "s": shoulder,
        "e": elbow,
        "h": wrist,
        "spd": speed,
        "acc": acceleration
    })


def return_home():
    if stop_event.is_set():
        return None

    return send_to_robot({"T": 100})


# ============================================================
# GESTURE HELPERS
# ============================================================

def interruptible_sleep(seconds):
    """
    Wait in short intervals so an application-level STOP can
    interrupt a gesture's waiting period.
    """
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False

        time.sleep(min(0.05, deadline - time.monotonic()))

    return not stop_event.is_set()


def perform_wave():
    movements = [
        ({"base": 0, "shoulder": 45, "elbow": 45, "wrist": 90}, 0.5),
        ({"base": -20, "shoulder": 45, "elbow": 45, "wrist": 90,
          "speed": 30}, 0.4),
        ({"base": 20, "shoulder": 45, "elbow": 45, "wrist": 90,
          "speed": 30}, 0.4),
        ({"base": 0, "shoulder": 0, "elbow": 90, "wrist": 180,
          "speed": 20, "acceleration": 10}, 0)
    ]

    for movement, delay in movements:
        if stop_event.is_set():
            return

        move_arm(**movement)

        if delay and not interruptible_sleep(delay):
            return


def perform_farewell():
    movements = [
        (70, 0.4),
        (120, 0.4),
        (70, 0.4)
    ]

    for wrist_angle, delay in movements:
        if stop_event.is_set():
            return

        move_arm(
            base=0,
            shoulder=45,
            elbow=45,
            wrist=wrist_angle,
            speed=20
        )

        if not interruptible_sleep(delay):
            return

    if not stop_event.is_set():
        return_home()


def perform_shake():
    movements = [
        (45, 0.8),
        (135, 0.3),
        (45, 0.3)
    ]

    for wrist_angle, delay in movements:
        if stop_event.is_set():
            return

        move_arm(
            base=0,
            shoulder=45,
            elbow=60,
            wrist=wrist_angle
        )

        if not interruptible_sleep(delay):
            return

    if not stop_event.is_set():
        return_home()


# ============================================================
# STOP HANDLING
# ============================================================

def stop_arm():
    """
    Stop further application-level gesture commands.

    IMPORTANT:
    This does not send a physical emergency-stop payload.
    The correct firmware-specific stop command must be verified.
    """
    global latest_status

    stop_event.set()

    latest_status = (
        "STOP requested: application gesture sequence interrupted. "
        "Use the robot's verified physical stop if it is still moving."
    )

    print(latest_status)


# ============================================================
# VOICE COMMAND HANDLER
# ============================================================

def trigger_keyword_gesture(phrase):
    global latest_status

    text = phrase.lower().strip()

    if not text:
        return

    words = text.split()

    # STOP takes priority over every ordinary command.
    if "stop" in words:
        stop_arm()
        return

    aliases = {
        "hello": "hi",
        "wave": "hi",
        "hi": "hi",

        "bye": "bye",
        "goodbye": "bye",

        "right": "right",
        "left": "left",
        "up": "up",
        "down": "down",

        "no": "no",
        "shake": "no",

        "open": "open",
        "release": "open",

        "close": "close",
        "clamp": "close",

        "home": "home",
        "center": "home",

        "sleep": "sleep"
    }

    matched = next(
        (aliases[word] for word in words if word in aliases),
        None
    )

    if matched is None:
        latest_status = f"Ignored unrecognized command: {text}"
        print(latest_status)
        return

    # Do not allow ordinary commands while STOP is active.
    if stop_event.is_set():
        latest_status = (
            "Robot commands are locked after STOP. "
            "Use the dashboard Reset button after checking safety."
        )
        return

    if not robot_lock.acquire(blocking=False):
        latest_status = "Robot is busy executing another command."
        return

    try:
        # STOP may have been activated while waiting for the lock.
        if stop_event.is_set():
            return

        print(f"Executing command: {matched}")

        if matched == "hi":
            perform_wave()
            if not stop_event.is_set():
                latest_status = "Greeting gesture completed."

        elif matched == "bye":
            perform_farewell()
            if not stop_event.is_set():
                latest_status = "Farewell gesture completed."

        elif matched == "right":
            move_arm(
                base=15,
                shoulder=45,
                elbow=45,
                wrist=90
            )
            if not stop_event.is_set():
                latest_status = "Right command sent."

        elif matched == "left":
            move_arm(
                base=-15,
                shoulder=45,
                elbow=45,
                wrist=90
            )
            if not stop_event.is_set():
                latest_status = "Left command sent."

        elif matched == "up":
            move_arm(
                base=0,
                shoulder=30,
                elbow=60,
                wrist=90
            )
            if not stop_event.is_set():
                latest_status = "Up command sent."

        elif matched == "down":
            move_arm(
                base=0,
                shoulder=60,
                elbow=30,
                wrist=90
            )
            if not stop_event.is_set():
                latest_status = "Down command sent."

        elif matched == "no":
            perform_shake()
            if not stop_event.is_set():
                latest_status = "Shake gesture completed."

        elif matched == "open":
            if not stop_event.is_set():
                result = send_to_robot({
                    "T": 106,
                    "cmd": 3.14,
                    "spd": 0,
                    "acc": 0
                })

                if not stop_event.is_set():
                    latest_status = (
                        "Opening gripper command sent."
                        if result is not None
                        else "Failed to send gripper command."
                    )

        elif matched == "close":
            if not stop_event.is_set():
                result = send_to_robot({
                    "T": 106,
                    "cmd": 0.5,
                    "spd": 0,
                    "acc": 0
                })

                if not stop_event.is_set():
                    latest_status = (
                        "Closing gripper command sent."
                        if result is not None
                        else "Failed to send gripper command."
                    )

        elif matched == "home":
            return_home()
            if not stop_event.is_set():
                latest_status = "Home command sent."

        elif matched == "sleep":
            move_arm(
                base=0,
                shoulder=85,
                elbow=145,
                wrist=180,
                speed=10,
                acceleration=5
            )
            if not stop_event.is_set():
                latest_status = "Sleep command sent."

    finally:
        robot_lock.release()


# ============================================================
# RESET AFTER STOP
# ============================================================

def reset_stop_state():
    """
    Clear the software STOP latch.

    This only enables future commands. It does not stop, reset,
    or verify the physical state of the robot.
    """
    global latest_status

    stop_event.clear()
    latest_status = (
        "Software STOP cleared. Check the robot is safe before "
        "sending another movement command."
    )

    print(latest_status)


# ============================================================
# OFFLINE VOICE RECOGNITION
# ============================================================

def voice_listener_thread():
    global latest_status
    global current_mic_volume
    global last_spoken_sentence

    print("=" * 55)
    print("Initializing offline Vosk voice recognition...")
    print(f"Looking for model at: {MODEL_PATH}")
    print("=" * 55)

    if not os.path.isdir(MODEL_PATH):
        latest_status = "Setup error: Vosk model folder missing."
        last_spoken_sentence = latest_status
        print(f"ERROR: Model folder not found: {MODEL_PATH}")
        return

    audio = None
    stream = None

    try:
        model = Model(MODEL_PATH)

        grammar = [
            "hello", "hi", "wave",
            "bye", "goodbye",
            "right", "left", "up", "down",
            "no", "shake",
            "open", "release",
            "close", "clamp",
            "home", "center",
            "sleep", "stop",
            "[unk]"
        ]

        recognizer = KaldiRecognizer(
            model,
            SAMPLE_RATE,
            json.dumps(grammar)
        )

        audio = pyaudio.PyAudio()

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER
        )

        stream.start_stream()

        latest_status = "Voice recognition active. Speak a command."

        print("Voice recognition is active.")
        print(
            "Commands: Hi, Bye, Right, Left, Up, Down, "
            "Shake, Open, Close, Home, Sleep, STOP"
        )
        print("=" * 55)

        while True:
            data = stream.read(
                4000,
                exception_on_overflow=False
            )

            if not data:
                continue

            raw_data = np.frombuffer(data, dtype=np.int16)

            rms = np.sqrt(
                np.mean(raw_data.astype(np.float64) ** 2)
            )

            current_mic_volume = min(int(rms / 15), 100)

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                phrase = result.get("text", "").strip()

                if phrase:
                    print(f"Recognized speech: {phrase}")
                    last_spoken_sentence = phrase
                    trigger_keyword_gesture(phrase)

    except Exception as exc:
        latest_status = "Voice recognition initialization or audio error."
        last_spoken_sentence = latest_status
        print(f"Voice recognition error: {exc}")

    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

        if audio is not None:
            try:
                audio.terminate()
            except Exception:
                pass


# ============================================================
# DASHBOARD ACTION API
# ============================================================

@app.route("/action/<keyword>", methods=["POST"])
def action_endpoint(keyword):
    global last_spoken_sentence

    allowed_commands = {
        "hello", "hi", "wave",
        "bye", "goodbye",
        "right", "left", "up", "down",
        "no", "shake",
        "open", "release",
        "close", "clamp",
        "home", "center",
        "sleep", "stop"
    }

    keyword = keyword.lower().strip()

    if keyword not in allowed_commands:
        return jsonify({
            "success": False,
            "status": "Unknown command."
        }), 400

    last_spoken_sentence = f"Dashboard action: {keyword}"

    # STOP is handled immediately without waiting for robot_lock.
    if keyword == "stop":
        stop_arm()
        return jsonify({
            "success": True,
            "status": latest_status
        })

    threading.Thread(
        target=trigger_keyword_gesture,
        args=(keyword,),
        daemon=True
    ).start()

    return jsonify({
        "success": True,
        "status": f"Command received: {keyword}"
    })


@app.route("/action/reset-stop", methods=["POST"])
def reset_stop_endpoint():
    reset_stop_state()

    return jsonify({
        "success": True,
        "status": latest_status
    })


# ============================================================
# TELEMETRY API
# ============================================================

@app.route("/telemetry")
def telemetry_endpoint():
    return jsonify({
        "status": latest_status,
        "volume": current_mic_volume,
        "sentence": last_spoken_sentence,
        "stopped": stop_event.is_set()
    })


# ============================================================
# DASHBOARD
# ============================================================

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Urban Ebot Controller</title>

<style>
body {
    font-family: Arial, sans-serif;
    background: #121216;
    color: white;
    text-align: center;
    padding: 20px;
    margin: 0;
}
.wrapper { max-width: 650px; margin: auto; }
h1 { color: #00ff66; }
.panel {
    background: #1c1c24;
    border: 1px solid #33333f;
    border-radius: 10px;
    padding: 18px;
    margin-bottom: 18px;
}
.vu-track {
    height: 15px;
    background: #09090d;
    border-radius: 8px;
    overflow: hidden;
}
.vu-fill {
    height: 100%;
    width: 0%;
    background: #00ff66;
    transition: width .1s;
}
.speech {
    background: #09090d;
    color: #00ff66;
    padding: 15px;
    margin-top: 12px;
    overflow-wrap: anywhere;
}
.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}
button {
    background: #1c1c24;
    color: #00ff66;
    border: 2px solid #00ff66;
    border-radius: 8px;
    padding: 16px 8px;
    font-weight: bold;
    cursor: pointer;
}
button:hover {
    background: #00ff66;
    color: #121216;
}
button:disabled { opacity: .5; }
.stop-button {
    width: 100%;
    background: #dc2626;
    color: white;
    border: 3px solid #ff7777;
    font-size: 23px;
    padding: 20px;
    margin-bottom: 12px;
}
.stop-button:hover {
    background: #991b1b;
    color: white;
}
.reset-button {
    width: 100%;
    background: #8a5a00;
    color: white;
    border-color: #ffc107;
    margin-bottom: 18px;
}
.status {
    text-align: left;
    overflow-wrap: anywhere;
    color: #ccc;
}
.commands { color: #ccc; line-height: 1.8; }
.warning {
    color: #ffb4b4;
    font-size: 13px;
    line-height: 1.6;
}
@media(max-width:480px) {
    body { padding: 10px; }
    h1 { font-size: 22px; }
}
</style>
</head>

<body>
<div class="wrapper">
    <h1>🤖 Urban Ebot Controller</h1>
    <p>Offline Voice Recognition and RoArm-M2-S Control</p>

    <div class="panel">
        <p>🎙️ Microphone Activity: <span id="vu-pct">0%</span></p>
        <div class="vu-track">
            <div class="vu-fill" id="vu-bar"></div>
        </div>
        <p>Recognized Speech</p>
        <div class="speech" id="speech-render">
            Waiting for voice commands...
        </div>
    </div>

    <div class="panel commands">
        <strong>Voice commands</strong><br>
        Hi / Hello / Wave — Greeting gesture<br>
        Bye / Goodbye — Farewell gesture<br>
        Right / Left — Rotate base<br>
        Up / Down — Adjust arm joints<br>
        Open / Release — Open gripper<br>
        Close / Clamp — Close gripper<br>
        Home / Center — Home position<br>
        Sleep — Sleep position<br>
        <strong style="color:#ff7777">STOP — Cancel further gesture steps</strong>
        <p class="warning">
            Software STOP is not a verified hardware emergency stop.
            If the robot keeps moving, use its physical stop/power procedure.
        </p>
    </div>

    <button
        class="stop-button"
        onclick="fireAction('stop', this)">
        🛑 STOP
    </button>

    <button
        class="reset-button"
        onclick="resetStop(this)">
        ⚠️ RESET SOFTWARE STOP
    </button>

    <div class="grid">
        <button onclick="fireAction('hi', this)">👋 Hi / Wave</button>
        <button onclick="fireAction('bye', this)">👋 Bye</button>
        <button onclick="fireAction('right', this)">➡️ Right</button>
        <button onclick="fireAction('left', this)">⬅️ Left</button>
        <button onclick="fireAction('up', this)">⬆️ Up</button>
        <button onclick="fireAction('down', this)">⬇️ Down</button>
        <button onclick="fireAction('no', this)">❌ Shake</button>
        <button onclick="fireAction('open', this)">👐 Open Gripper</button>
        <button onclick="fireAction('close', this)">✊ Close Gripper</button>
        <button onclick="fireAction('home', this)">🏠 Home</button>
        <button onclick="fireAction('sleep', this)">😴 Sleep</button>
    </div>

    <div class="panel status" id="log-footer">
        Status: Connecting to Flask server...
    </div>
</div>

<script>
async function fireAction(keyword, button) {
    button.disabled = true;

    try {
        const response = await fetch(`/action/${keyword}`, {
            method: 'POST'
        });

        const data = await response.json();

        document.getElementById('log-footer').innerText =
            'Status: ' + data.status;
    } catch (error) {
        document.getElementById('log-footer').innerText =
            'Unable to contact Flask server.';
    } finally {
        button.disabled = false;
    }
}

async function resetStop(button) {
    const confirmed = confirm(
        'Only reset after checking that the robot is safe. ' +
        'This clears the software lock; it does not verify the robot state. Continue?'
    );

    if (!confirmed) {
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch('/action/reset-stop', {
            method: 'POST'
        });

        const data = await response.json();

        document.getElementById('log-footer').innerText =
            'Status: ' + data.status;
    } catch (error) {
        document.getElementById('log-footer').innerText =
            'Unable to contact Flask server.';
    } finally {
        button.disabled = false;
    }
}

async function updateTelemetry() {
    try {
        const response = await fetch('/telemetry');
        const data = await response.json();

        document.getElementById('log-footer').innerText =
            'Status: ' + data.status;

        document.getElementById('vu-bar').style.width =
            data.volume + '%';

        document.getElementById('vu-pct').innerText =
            data.volume + '%';

        document.getElementById('speech-render').innerText =
            data.sentence;
    } catch (error) {
        document.getElementById('log-footer').innerText =
            'Connection to Flask server failed.';
    }
}

setInterval(updateTelemetry, 250);
updateTelemetry();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_DASHBOARD)


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    threading.Thread(
        target=voice_listener_thread,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )