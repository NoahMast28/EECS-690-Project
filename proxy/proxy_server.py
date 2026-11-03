"""
NAO WoZ Proxy - command relay between Tkinter controller, quiz pages, and NAO bridge.
Deploy on Render.com / Fly.io. Set env vars: PROXY_TOKEN, PORT (default 5000).
"""
import os, json, time, threading, queue
from collections import deque
from flask import Flask, request, jsonify
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

AUTH_TOKEN = os.environ.get("PROXY_TOKEN", "change-me-in-production")
MAX_HISTORY = 200

lock = threading.Lock()
command_history = deque(maxlen=MAX_HISTORY)
command_counter = 0
quiz_clients = set()
bridge_clients = set()


class WSClient:
    """Thread-safe wrapper: HTTP handler threads enqueue, dedicated writer thread sends."""
    def __init__(self, ws):
        self.ws = ws
        self.q = queue.Queue()
        self.alive = True

    def enqueue(self, payload: str):
        if self.alive:
            self.q.put(payload)

    def close(self):
        self.alive = False
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass


def broadcast(clients, msg: dict):
    payload = json.dumps(msg)
    with lock:
        targets = list(clients)
    for c in targets:
        c.enqueue(payload)


def _auth_ok():
    h = request.headers.get("Authorization", "")
    return h.startswith("Bearer ") and h[7:] == AUTH_TOKEN


@app.route("/api/command", methods=["POST"])
def receive_command():
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True) or {}
    if "action" not in data:
        return jsonify({"error": "action required"}), 400

    global command_counter
    with lock:
        command_counter += 1
        cmd = {
            "id": command_counter,
            "ts": time.time(),
            "action": data["action"],
            "payload": data.get("payload", {}),
            "target": data.get("target", "nao"),   # "nao" | "quiz" | "both"
            "status": "dispatched",
        }
        command_history.append(cmd)

    if cmd["target"] in ("nao", "both"):
        broadcast(bridge_clients, cmd)
    if cmd["target"] in ("quiz", "both"):
        broadcast(quiz_clients, cmd)

    return jsonify({"id": cmd["id"], "status": "dispatched"})


@app.route("/api/status", methods=["GET"])
def status():
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    with lock:
        return jsonify({
            "command_count": command_counter,
            "quiz_clients": len(quiz_clients),
            "bridge_clients": len(bridge_clients),
            "recent": list(command_history)[-10:],
        })


def _run_ws(ws, client_set, kind):
    token = request.args.get("token", "")
    if token != AUTH_TOKEN:
        ws.close()
        return

    client = WSClient(ws)
    with lock:
        client_set.add(client)

    def writer():
        while client.alive:
            msg = client.q.get()
            if msg is None:
                break
            try:
                ws.send(msg)
            except Exception:
                client.close()
                break

    threading.Thread(target=writer, daemon=True).start()

    try:
        while client.alive:
            raw = ws.receive()
            if raw is None:
                break
            # Bridge sends acks: {"id": 5, "status": "done"}
            if kind == "bridge":
                try:
                    ack = json.loads(raw)
                    cid = ack.get("id")
                    new_status = ack.get("status", "done")
                    with lock:
                        for c in command_history:
                            if c["id"] == cid:
                                c["status"] = new_status
                                break
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        client.close()
        with lock:
            client_set.discard(client)


@sock.route("/ws/quiz")
def quiz_ws(ws):
    _run_ws(ws, quiz_clients, "quiz")


@sock.route("/ws/bridge")
def bridge_ws(ws):
    _run_ws(ws, bridge_clients, "bridge")


@app.route("/")
def index():
    with lock:
        return jsonify({
            "status": "ok",
            "quiz_clients": len(quiz_clients),
            "bridge_clients": len(bridge_clients),
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))