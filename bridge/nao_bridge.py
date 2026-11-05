"""
NAO Bridge - runs on the machine that can reach the robot (PC 1).
Bridges proxy WebSocket commands to NAOqi calls.

Usage:
  export PROXY_URL=wss://nao-proxy.onrender.com
  export PROXY_TOKEN=<same token>
  export NAO_IP=10.117.35.236
  python3 nao_bridge.py
"""
import os, json, time, sys
import websocket  # pip install websocket-client
import qi         # SoftBank's NAOqi Python SDK (already installed for your lab)

PROXY_URL = os.environ.get("PROXY_URL", "wss://nao-proxy.onrender.com").rstrip("/")
TOKEN     = os.environ.get("PROXY_TOKEN", "change-me-in-production")
NAO_IP    = os.environ.get("NAO_IP", "192.168.1.100")

session  = None
tts      = None
motion   = None
posture  = None
leds     = None
anim     = None


def connect_nao():
    global session, tts, motion, posture, leds, anim
    print(f"[bridge] connecting to NAO at {NAO_IP}:9559 ...")
    session = qi.Session()
    session.connect(f"tcp://{NAO_IP}:9559")
    tts     = session.service("ALTextToSpeech")
    motion  = session.service("ALMotion")
    posture = session.service("ALRobotPosture")
    leds    = session.service("ALLeds")
    anim    = session.service("ALAnimationPlayer")
    motion.wakeUp()
    print("[bridge] NAO ready")


def run_animation(path: str):
    """Play a pre-recorded animation by its full path, non-blocking."""
    anim.run(path, _async=True)


def execute(action: str, payload: dict):
    try:
        if action == "say":
            tts.say(payload.get("text", ""))

        elif action == "nod":
            # Explicitly programmed head nod (kept as-is)
            motion.angleInterpolation(
                ["HeadPitch"], [[0.2, -0.2, 0.0]], [[0.5, 1.0, 1.5]], True)

        elif action == "shake_head":
            run_animation("animations/Stand/Gestures/No_3")

        elif action == "wave":
            run_animation("animations/Stand/Gestures/Hey_1")

        elif action == "shrug":
            run_animation("animations/Stand/Gestures/IDontKnow_1")

        elif action == "laugh":
            run_animation("animations/Stand/Emotions/Positive/Laugh_1")

        elif action == "led":
            color = payload.get("color", "00FF00").lstrip("#")
            leds.fadeRGB("FaceLeds", int(color, 16), 1.0)

        elif action == "led_off":
            leds.off("FaceLeds")

        elif action == "posture":
            posture.goToPosture(payload.get("name", "Stand"), 0.5)

        elif action == "stop":
            motion.stopMove()

        else:
            return False, f"unknown action: {action}"

        return True, "ok"
    except Exception as e:
        return False, str(e)


def on_message(ws, message):
    try:
        cmd = json.loads(message)
        cid, action = cmd.get("id"), cmd.get("action")
        payload = cmd.get("payload", {}) or {}
        print(f"[bridge] <- #{cid} {action} {payload}")
        ok, msg = execute(action, payload)
        ws.send(json.dumps({"id": cid, "status": "done" if ok else "error", "message": msg}))
    except Exception as e:
        print(f"[bridge] handler error: {e}")


def on_open(ws):
    print(f"[bridge] connected to proxy {PROXY_URL}")
    ws.send(json.dumps({"type": "hello", "role": "bridge"}))


def on_error(ws, err):
    print(f"[bridge] ws error: {err}")


def on_close(ws, code, msg):
    print(f"[bridge] ws closed ({code}): {msg}")


def main():
    connect_nao()
    url = f"{PROXY_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/bridge?token={TOKEN}"
    while True:
        print(f"[bridge] connecting to proxy: {url}")
        try:
            ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            ws.run_forever()
        except Exception as e:
            print(f"[bridge] connect error: {e}")
        print("[bridge] reconnecting in 5s ...")
        time.sleep(5)


if __name__ == "__main__":
    main()