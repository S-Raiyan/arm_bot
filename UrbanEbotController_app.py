import os
import sys
import webbrowser
import json

import time

import random

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


def resource_path(relative_path):
    """Resolve bundled resources in development and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = BASE_DIR
    return os.path.join(base_path, relative_path)


MODEL_PATH = resource_path("model")

SAMPLE_RATE = 16000

FRAMES_PER_BUFFER = 8000

latest_status = "System online. Waiting for voice commands."

current_mic_volume = 0

last_spoken_sentence = "None"

current_emotion = "normal"

# Prevent multiple gestures from running simultaneously.

robot_lock = threading.Lock()

# Application-level STOP latch.

stop_event = threading.Event()

# Serialize HTTP requests.

http_lock = threading.Lock()

# ============================================================

# ROBOT COMMUNICATION

# ============================================================

def send_to_robot(payload):

    """Send a JSON command to the robot."""

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

    """Send a joint movement using the existing T=122 format."""

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

# GESTURE UTILITIES

# ============================================================

def interruptible_sleep(seconds):

    """Allow a gesture's waiting period to be interrupted by STOP."""

    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:

        if stop_event.is_set():

            return False

        time.sleep(min(0.05, deadline - time.monotonic()))

    return not stop_event.is_set()

def perform_sequence(movements):

    """

    Execute a sequence of (joint_arguments, delay) pairs.

    Stop scheduling further movements after STOP.

    """

    for movement, delay in movements:

        if stop_event.is_set():

            return False

        move_arm(**movement)

        if stop_event.is_set():

            return False

        if delay and not interruptible_sleep(delay):

            return False

    return not stop_event.is_set()

# ============================================================

# EXISTING GESTURES

# ============================================================

def perform_wave():

    movements = [

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 90

            },

            0.5

        ),

        (

            {

                "base": -20, "shoulder": 45,

                "elbow": 45, "wrist": 90,

                "speed": 30

            },

            0.4

        ),

        (

            {

                "base": 20, "shoulder": 45,

                "elbow": 45, "wrist": 90,

                "speed": 30

            },

            0.4

        ),

        (

            {

                "base": 0, "shoulder": 0,

                "elbow": 90, "wrist": 180,

                "speed": 20, "acceleration": 10

            },

            0

        )

    ]

    perform_sequence(movements)

def perform_farewell():

    movements = [

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 70,

                "speed": 20

            },

            0.4

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 120,

                "speed": 20

            },

            0.4

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 70,

                "speed": 20

            },

            0.4

        )

    ]

    if perform_sequence(movements):

        return_home()

def perform_shake():

    movements = [

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 60, "wrist": 45

            },

            0.5

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 60, "wrist": 135

            },

            0.3

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 60, "wrist": 45

            },

            0.3

        )

    ]

    if perform_sequence(movements):

        return_home()

# ============================================================

# EMOTIONAL ROBOT ACTIONS

# ============================================================

def set_emotion(emotion):

    global current_emotion

    current_emotion = emotion

def perform_sad():

    """Lower the arm to represent a sad emotion."""

    global latest_status

    set_emotion("sad")

    latest_status = "😢 Robot is feeling sad."

    movements = [

        (

            {

                "base": 0, "shoulder": 65,

                "elbow": 35, "wrist": 120,

                "speed": 15, "acceleration": 10

            },

            2

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 90,

                "speed": 15, "acceleration": 10

            },

            0

        )

    ]

    if perform_sequence(movements):

        set_emotion("normal")

        latest_status = "Sad gesture completed."

def perform_happy():

    """Raise the arm and perform a cheerful wrist wave."""

    global latest_status

    set_emotion("happy")

    latest_status = "😊 Robot is happy and ready to play!"

    movements = [

        (

            {

                "base": 0, "shoulder": 35,

                "elbow": 55, "wrist": 90,

                "speed": 20, "acceleration": 10

            },

            0.4

        )

    ]

    for wrist_angle in [65, 115, 65, 115, 90]:

        movements.append((

            {

                "base": 0, "shoulder": 35,

                "elbow": 55, "wrist": wrist_angle,

                "speed": 20, "acceleration": 10

            },

            0.3

        ))

    if perform_sequence(movements):

        set_emotion("normal")

        latest_status = "😊 Happy gesture completed!"

def perform_curious():

    """Perform a small gesture representing curiosity."""

    global latest_status

    set_emotion("curious")

    latest_status = "🤔 Robot is curious!"

    movements = [

        (

            {

                "base": 0, "shoulder": 35,

                "elbow": 45, "wrist": 110,

                "speed": 15, "acceleration": 10

            },

            1

        ),

        (

            {

                "base": 0, "shoulder": 45,

                "elbow": 45, "wrist": 90,

                "speed": 15, "acceleration": 10

            },

            0

        )

    ]

    if perform_sequence(movements):

        set_emotion("normal")

        latest_status = "Curious gesture completed."

def perform_give_rose():

    """Perform a dedicated rose-giving gesture using a lightweight rose attached to the gripper.

    Joint angles are conservative starting values only. Test and calibrate them

    for this robot before use. The software cannot detect whether a rose is attached.

    """

    global latest_status

    set_emotion("giving_rose")

    latest_status = "🌹 Preparing to offer a rose..."

    print(latest_status)

    # Open gripper first so the rose can be attached or released as intended.

    if stop_event.is_set():

        return False

    send_to_robot({"T": 106, "cmd": 3.14, "spd": 0, "acc": 0})

    if not interruptible_sleep(0.5):

        return False

    movements = [

        # Center the arm before presenting the rose.

        ({"base": 0, "shoulder": 45, "elbow": 55, "wrist": 90,

          "speed": 10, "acceleration": 8}, 0.7),

        # Lower the arm slightly in a gentle, respectful gesture.

        ({"base": 0, "shoulder": 55, "elbow": 62, "wrist": 95,

          "speed": 8, "acceleration": 6}, 0.8),

        # Extend the rose toward the recipient.

        ({"base": 0, "shoulder": 38, "elbow": 72, "wrist": 110,

          "speed": 8, "acceleration": 6}, 2.5),

    ]

    if not perform_sequence(movements):

        return False

    latest_status = "🌹 Here is a rose for you!"

    print(latest_status)

    if not interruptible_sleep(1.5):

        return False

    # Release the rose only if one is physically fitted and the pose is safe.

    if stop_event.is_set():

        return False

    send_to_robot({"T": 106, "cmd": 3.14, "spd": 0, "acc": 0})

    if not interruptible_sleep(0.7):

        return False

    # Retract slowly to a neutral pose.

    if not perform_sequence([

        ({"base": 0, "shoulder": 45, "elbow": 55, "wrist": 90,

          "speed": 8, "acceleration": 6}, 0),

    ]):

        return False

    set_emotion("normal")

    latest_status = "🌹 Rose-giving gesture completed!"

    print(latest_status)

    return True

def propose_action():

    """Run the dedicated rose-giving gesture; never selects Curious or Shake."""

    global latest_status

    if stop_event.is_set():

        latest_status = "Proposal cancelled: software STOP is active."

        return False

    return perform_give_rose()

def perform_crazy():

    """Perform three randomly proposed gestures, stopping safely if requested."""

    global latest_status

    set_emotion("crazy")

    latest_status = "🤪 Crazy mode activated! Choosing three actions..."

    print(latest_status)

    for index in range(3):

        if stop_event.is_set():

            return

        crazy_actions = [perform_wave, perform_happy, perform_curious, perform_shake]

        action = random.choice(crazy_actions)

        if stop_event.is_set():

            return

        action()

        if stop_event.is_set():

            return

        if index < 2 and not interruptible_sleep(0.5):

            return

    if not stop_event.is_set():

        set_emotion("normal")

        latest_status = "🤪 Crazy mode completed!"

        print(latest_status)

def write_a(speed=500, acceleration=100, dwell_time=1):

    """

    Experimental letter-A drawing sequence.

    Joint angles are starting examples and must be calibrated

    for your robot, pen holder, and writing surface.

    """

    if speed <= 0:

        raise ValueError("speed must be positive")

    if acceleration <= 0:

        raise ValueError("acceleration must be positive")

    if dwell_time <= 0:

        raise ValueError("dwell_time must be positive")

    if stop_event.is_set():

        return False

    # Replace these example poses with calibrated positions.

    # Format: base, shoulder, elbow, wrist

    poses = [

        (0,  30,  30,  0),   # Start near bottom-left

        (0,  50,  10,  0),   # Move toward top

        (0,  30, -10,  0),   # Move toward bottom-right

        (0,  40,  10,  0),   # Move toward middle for crossbar

    ]

    try:

        for base, shoulder, elbow, wrist in poses:

            if stop_event.is_set():

                return False

            success = move_arm(

                base=base,

                shoulder=shoulder,

                elbow=elbow,

                wrist=wrist,

                speed=speed,

                acceleration=acceleration

            )

            if not success:

                return False

            time.sleep(dwell_time)

        return True

    except Exception as exc:

        print(f"Could not complete letter A: {exc}")

        return False

# ============================================================

# STOP HANDLING

# ============================================================

def stop_arm():

    """

    Interrupt future application-level gesture steps.

    This is NOT a verified physical emergency stop.

    """

    global latest_status

    stop_event.set()

    set_emotion("stopped")

    latest_status = (

        "🛑 STOP requested. Further gesture steps are blocked. "

        "If the robot is still moving, use its verified physical stop."

    )

    print(latest_status)

def reset_stop_state():

    """Clear the software STOP latch when no gesture is running."""

    global latest_status

    if robot_lock.locked():

        return False

    stop_event.clear()

    set_emotion("normal")

    latest_status = (

        "Software STOP cleared. Check the robot is safe "

        "before sending another command."

    )

    print(latest_status)

    return True

# ============================================================

# VOICE COMMAND HANDLER

# ============================================================

def trigger_keyword_gesture(phrase):

    global latest_status

    text = phrase.lower().strip().replace("-", " ")

    if not text:

        return

    words = text.split()

    # STOP always takes priority.

    if "stop" in words:

        stop_arm()

        return

    # Match specific phrases before generic words.

    phrase_aliases = {

        "goodbye": "bye",

        "good bye": "bye",

        "hello": "hi",

        "hi": "hi",

        "wave": "hi",

        "can i play with you": "happy",

        "lets play": "happy",

        "let's play": "happy",

        "play with me": "happy",

        "bad robot": "sad",

        "you are bad": "sad",

        "youre bad": "sad",

        "you are a bad robot": "sad",

        "surprise me": "crazy",

        "make me laugh": "crazy",

        "im bored": "crazy",

        "i am bored": "crazy",

        "propose action": "propose",

        "suggest an action": "propose",

        "write letter a": "write_a",

        "write a": "write_a"

    }

    matched = None

    # Match phrases first.

    for phrase_alias, command in sorted(

        phrase_aliases.items(),

        key=lambda item: len(item[0]),

        reverse=True

    ):

        if phrase_alias in text:

            matched = command

            break

    # If no phrase matches, use individual command words.

    if matched is None:

        aliases = {

            "hello": "hi",

            "hi": "hi",

            "wave": "hi",

            "bye": "bye",

            "goodbye": "bye",

            "right": "right",

            "left": "left",

            "up": "up",

            "down": "down",

            "no": "sad",

            "bad": "sad",

            "sad": "sad",

            "yes": "happy",

            "play": "happy",

            "game": "happy",

            "happy": "happy",

            "crazy": "crazy",

            "bored": "crazy",

            "surprise": "crazy",

            "dance": "crazy",

            "curious": "curious",

            "propose": "propose",

            "write": "write_a",

            "shake": "shake",

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

    if stop_event.is_set():

        latest_status = (

            "Commands locked after STOP. Check robot safety, "

            "then use Reset Software STOP."

        )

        return

    if not robot_lock.acquire(blocking=False):

        latest_status = "Robot is busy executing another command."

        return

    try:

        if stop_event.is_set():

            return

        print(f"Executing command: {matched}")

        # Greeting and farewell

        if matched == "hi":

            perform_wave()

            if not stop_event.is_set():

                latest_status = "👋 Greeting gesture completed."

        elif matched == "bye":

            perform_farewell()

            if not stop_event.is_set():

                latest_status = "👋 Farewell gesture completed."

        # Directions

        elif matched == "right":

            move_arm(

                base=15, shoulder=45,

                elbow=45, wrist=90

            )

            if not stop_event.is_set():

                latest_status = "➡️ Right command sent."

        elif matched == "left":

            move_arm(

                base=-15, shoulder=45,

                elbow=45, wrist=90

            )

            if not stop_event.is_set():

                latest_status = "⬅️ Left command sent."

        elif matched == "up":

            move_arm(

                base=0, shoulder=30,

                elbow=60, wrist=90

            )

            if not stop_event.is_set():

                latest_status = "⬆️ Up command sent."

        elif matched == "down":

            move_arm(

                base=0, shoulder=60,

                elbow=30, wrist=90

            )

            if not stop_event.is_set():

                latest_status = "⬇️ Down command sent."

        # Emotions

        elif matched == "sad":

            perform_sad()

        elif matched == "happy":

            perform_happy()

        elif matched == "crazy":

            perform_crazy()

        elif matched == "curious":

            perform_curious()

        elif matched == "propose":

            if propose_action() and not stop_event.is_set():

                latest_status = "🤖 Proposed action completed!"

        elif matched == "shake":

            perform_shake()

            if not stop_event.is_set():

                latest_status = "Shake gesture completed."

        # Gripper

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

        # Home and sleep

        elif matched == "home":

            return_home()

            if not stop_event.is_set():

                latest_status = "🏠 Home command sent."

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

                latest_status = "😴 Sleep command sent."

        elif matched == "write_a":

            result = write_a()

            if not stop_event.is_set():

                latest_status= ( "Letter A sequence completed."

                                if result

                                else "Letter A sequence stopped or failed.")

    finally:

            robot_lock.release()

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

            "no", "bad", "sad",

            "yes", "play", "game", "happy",

            "crazy", "bored", "surprise",

            "dance", "curious",

            "shake",

            "open", "release",

            "close", "clamp",

            "write", "a", "write a", "write letter a",

            "propose", "propose action", "suggest an action",

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

            "No, Yes, Bad, Play, Crazy, Dance, Curious, "

            "Shake, Open, Close, Home, Sleep, STOP, Write A, Propose"

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

        latest_status = (

            "Voice recognition initialization or audio error."

        )

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

        "no", "bad", "sad",

        "yes", "play", "game", "happy",

        "crazy", "bored", "surprise",

        "dance", "curious", "propose", "propose-action",

        "shake",

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

    # STOP does not wait for the robot movement lock.

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

    success = reset_stop_state()

    if not success:

        return jsonify({

            "success": False,

            "status": (

                "A gesture is still finishing its interruption. "

                "Wait briefly, verify the robot is safe, then reset."

            )

        }), 409

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

        "emotion": current_emotion,

        "stopped": stop_event.is_set()

    })

# ===============================================================

# To write A API

# ===============================================================

@app.route("/action/write-a", methods=["POST"])

def action_write_a():

    if stop_event.is_set():

        return {"success": False, "message": "Robot is stopped. Reset STOP first."}, 409

    # Use the shared command handler so this action respects robot_lock.

    threading.Thread(

        target=trigger_keyword_gesture,

        args=("write a",),

        daemon=True

    ).start()

    return {"success": True, "message": "Starting letter A sequence"}

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

.wrapper { max-width: 700px; margin: auto; }

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

.dedicated-propose {

    margin-top: 18px;

    padding: 14px;

    border: 1px solid #6d5dfc;

    border-radius: 12px;

    background: #171525;

}

.propose-button {

    display: block;

    width: 100%;

    padding: 20px 12px;

    font-size: 1.05rem;

    background: #6d5dfc;

    color: #ffffff;

    border: 2px solid #a59cff;

    border-radius: 10px;

}

.propose-button:hover {

    background: #5142d8;

    color: #ffffff;

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

.emotion-button {

    border-color: #b69cff;

    color: #d7c9ff;

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

    <p>Offline Voice Recognition and Emotional Robot Actions</p>

    <div class="panel">

        <p>🎙️ Microphone Activity: <span id="vu-pct">0%</span></p>

        <div class="vu-track">

            <div class="vu-fill" id="vu-bar"></div>

        </div>

        <p>Recognized Speech</p>

        <div class="speech" id="speech-render">

            Waiting for voice commands...

        </div>

        <p>Current emotion: <strong id="emotion">NORMAL</strong></p>

    </div>

    <div class="panel commands">

        <strong>Movement commands</strong><br>

        Hi / Hello / Wave — Greeting gesture<br>

        Bye / Goodbye — Farewell gesture<br>

        Right / Left — Rotate base<br>

        Up / Down — Adjust arm joints<br>

        Shake — Shake gesture<br>

        Open / Release — Open gripper<br>

        Close / Clamp — Close gripper<br>

        Home / Center — Home position<br>

        Sleep — Sleep position<br>

        write A/A — To write the A

        <br><br>

        <strong>Emotional commands</strong><br>

        No / Bad / Sad — Sad gesture<br>

        Yes / Play / Game — Happy gesture<br>

        Crazy / Bored / Surprise / Dance — Random playful gesture<br>

        Curious — Curious gesture

        <p class="warning">

            Software STOP interrupts future application gesture steps.

            It is not a verified physical emergency stop. Use the

            robot's verified physical stop if it continues moving.

        </p>

    </div>

    <button class="stop-button"

        onclick="fireAction('stop', this)">

        🛑 STOP

    </button>

    <button class="reset-button"

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

        <button onclick="fireAction('shake', this)">❌ Shake</button>

        <button onclick="fireAction('open', this)">👐 Open Gripper</button>

        <button onclick="fireAction('close', this)">✊ Close Gripper</button>

        <button onclick="fireAction('home', this)">🏠 Home</button>

        <button onclick="fireAction('sleep', this)">😴 Sleep</button>

        <button onclick="fireAction('sad', this)">😢 Sad Mode</button>

        <button onclick="fireAction('happy', this)">😊 Happy Mode</button>

        <button onclick="fireAction('crazy', this)">🤪 Crazy Mode</button>

        <button onclick="fireAction('curious', this)">🤔 Curious Mode</button>

        <button onclick="runAction('write-a')">✍️ WRITE A</button>

    </div>

    <div class="dedicated-propose">

        <button class="propose-button" onclick="fireAction('propose', this)">🤖 PROPOSE AN ACTION</button>

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

        'Check that the robot is safe before resetting. ' +

        'This only clears the software lock. Continue?'

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

        document.getElementById('emotion').innerText =

            (data.emotion || 'normal').toUpperCase();

    } catch (error) {

        document.getElementById('log-footer').innerText =

            'Connection to Flask server failed.';

    }

}

async function runAction(action) {

    try {

        const response = await fetch(`/action/${action}`, {

            method: "POST"

        });

        const result = await response.json();

        if (!response.ok) {

            alert(result.message || "Action failed");

            return;

        }

        document.getElementById('log-footer').innerText =

            'Status: ' + (result.message || result.status || 'Command received');

    } catch (error) {

        console.error("Robot action failed:", error);

        alert("Could not connect to the robot controller.");

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
    # Start offline voice recognition in the background.
    threading.Thread(target=voice_listener_thread, daemon=True).start()

    # Open the dashboard after Flask has had time to start.
    threading.Timer(
        1.5,
        lambda: webbrowser.open("http://127.0.0.1:5000")
    ).start()

    # Local-only dashboard is safer for a desktop application.
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
