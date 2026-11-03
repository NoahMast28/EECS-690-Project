#!/usr/bin/env python3
"""
trivia_server.py

Serves a small trivia website AND a tiny JSON API so an external
"Wizard of Oz" control panel (see nao_woz_gui.py) can drive the quiz.

Run:    python3 trivia_server.py
Open:   http://127.0.0.1:8000

API
---
GET  /api/state           -> full quiz state (never leaks the answer before confirm)
POST /api/start           -> start / restart the quiz
POST /api/select  {"index": 0..3}
POST /api/confirm
POST /api/next
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"   # use "0.0.0.0" if the browser runs on another machine
PORT = 8000

# --------------------------------------------------------------------------
# Quiz content (placeholder questions -- swap in real ones later)
# "answer" is the zero-based index of the correct option.
# --------------------------------------------------------------------------
QUESTIONS = [
    {
        "text": "Example question 1",
        "options": ["Answer 1", "Answer 2", "Answer 3", "Answer 4"],
        "answer": 0,
    },
    {
        "text": "Example question 2",
        "options": ["Answer 1", "Answer 2", "Answer 3", "Answer 4"],
        "answer": 0,
    },
    {
        "text": "Example question 3",
        "options": ["Answer 1", "Answer 2", "Answer 3", "Answer 4"],
        "answer": 0,
    },
]

# --------------------------------------------------------------------------
# Shared state
# --------------------------------------------------------------------------
_lock = threading.Lock()
_state = {
    "started": False,
    "finished": False,
    "index": 0,
    "selected": None,     # None or 0..3
    "confirmed": False,
}


def start_quiz():
    with _lock:
        _state.update(started=True, finished=False, index=0,
                      selected=None, confirmed=False)


def select_option(index):
    if not isinstance(index, int) or not (0 <= index < 4):
        return
    with _lock:
        if not _state["started"] or _state["finished"] or _state["confirmed"]:
            return
        _state["selected"] = index


def confirm_choice():
    with _lock:
        if not _state["started"] or _state["finished"] or _state["confirmed"]:
            return
        if _state["selected"] is None:
            return
        _state["confirmed"] = True


def next_question():
    with _lock:
        if not _state["started"] or _state["finished"] or not _state["confirmed"]:
            return
        if _state["index"] + 1 >= len(QUESTIONS):
            _state["finished"] = True
        else:
            _state["index"] += 1
            _state["selected"] = None
            _state["confirmed"] = False


def snapshot():
    """A JSON-safe view of the quiz, safe to show to the participant."""
    with _lock:
        s = dict(_state)

    base = {
        "started": s["started"],
        "finished": s["finished"],
        "index": s["index"],
        "total": len(QUESTIONS),
        "question": None,
        "options": [],
        "selected": s["selected"],
        "confirmed": s["confirmed"],
        "correct": None,
        "answer": None,
    }

    if not s["started"] or s["finished"]:
        return base

    q = QUESTIONS[s["index"]]
    base["question"] = q["text"]
    base["options"] = list(q["options"])
    if s["confirmed"]:
        base["correct"] = (s["selected"] == q["answer"])
        base["answer"] = q["answer"]
    return base


# --------------------------------------------------------------------------
# The website
# --------------------------------------------------------------------------
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trivia Quiz</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; padding: 20px;
    display: flex; align-items: center; justify-content: center;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: linear-gradient(160deg, #eef2ff, #e0f2fe);
    color: #0f172a;
  }
  .card {
    width: 100%; max-width: 560px; background: #fff;
    border-radius: 16px; padding: 28px;
    box-shadow: 0 20px 40px rgba(15, 23, 42, .12);
  }
  h1 { margin: 0 0 6px; font-size: 22px; }
  .progress {
    margin: 0 0 18px; font-size: 12px; color: #64748b;
    text-transform: uppercase; letter-spacing: .09em; min-height: 15px;
  }
  .question { font-size: 19px; font-weight: 600; margin: 0 0 18px; min-height: 26px; }
  .options { display: grid; gap: 10px; margin-bottom: 16px; }
  .option {
    text-align: left; padding: 14px 16px; font-size: 16px;
    font-family: inherit; color: inherit; cursor: pointer;
    border: 2px solid #e2e8f0; border-radius: 10px; background: #f8fafc;
    transition: background .12s ease, border-color .12s ease;
  }
  .option:hover:not(:disabled) { border-color: #6366f1; background: #eef2ff; }
  .option.selected  { border-color: #6366f1; background: #e0e7ff; }
  .option.correct   { border-color: #16a34a; background: #dcfce7; }
  .option.incorrect { border-color: #dc2626; background: #fee2e2; }
  .option:disabled  { cursor: default; }
  .feedback { min-height: 24px; margin: 0 0 14px; font-weight: 600; }
  .feedback.correct   { color: #15803d; }
  .feedback.incorrect { color: #b91c1c; }
  .buttons { display: flex; gap: 10px; }
  button.primary {
    padding: 12px 20px; border: none; border-radius: 10px;
    background: #4f46e5; color: #fff; font-size: 15px;
    font-weight: 600; font-family: inherit; cursor: pointer;
  }
  button.primary:hover:not(:disabled) { background: #4338ca; }
  button.primary:disabled { background: #c7d2fe; cursor: not-allowed; }
  .hidden { display: none !important; }
</style>
</head>
<body>
<main class="card">
  <h1>Trivia Quiz</h1>
  <p class="progress" id="progress"></p>
  <p class="question" id="question">Press “Start Quiz” to begin.</p>
  <div class="options" id="options"></div>
  <p class="feedback" id="feedback"></p>
  <div class="buttons">
    <button class="primary" id="startBtn">Start Quiz</button>
    <button class="primary hidden" id="confirmBtn">Confirm Choice</button>
    <button class="primary hidden" id="nextBtn">Next Question</button>
  </div>
</main>

<script>
const $ = (id) => document.getElementById(id);
let state = null;
let busy = false;
let lastKey = "";

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

async function post(path, body) {
  busy = true;
  try {
    state = await api(path, body || {});
    render();
  } catch (e) {
    console.error(e);
  } finally {
    busy = false;
  }
}

async function poll() {
  if (!busy) {
    try {
      const s = await api("/api/state");
      if (!busy) { state = s; render(); }
    } catch (e) { /* server not up yet */ }
  }
  setTimeout(poll, 250);
}

function letter(i) { return String.fromCharCode(65 + i); }

function render() {
  if (!state) return;
  const key = JSON.stringify(state);
  if (key === lastKey) return;
  lastKey = key;

  const s = state;

  // --- start button -----------------------------------------------------
  $("startBtn").textContent = s.started ? "Restart Quiz" : "Start Quiz";
  $("startBtn").classList.toggle("hidden", s.started && !s.finished);

  // --- not started ------------------------------------------------------
  if (!s.started) {
    $("progress").textContent = "";
    $("question").textContent = "Press “Start Quiz” to begin.";
    $("options").innerHTML = "";
    $("feedback").textContent = "";
    $("feedback").className = "feedback";
    $("confirmBtn").classList.add("hidden");
    $("nextBtn").classList.add("hidden");
    return;
  }

  // --- finished ---------------------------------------------------------
  if (s.finished) {
    $("progress").textContent = "";
    $("question").textContent = "Quiz complete — thanks for playing!";
    $("options").innerHTML = "";
    $("feedback").textContent = "";
    $("feedback").className = "feedback";
    $("confirmBtn").classList.add("hidden");
    $("nextBtn").classList.add("hidden");
    return;
  }

  // --- in progress ------------------------------------------------------
  $("progress").textContent = `Question ${s.index + 1} of ${s.total}`;
  $("question").textContent = s.question;

  const box = $("options");
  box.innerHTML = "";
  s.options.forEach((label, i) => {
    const btn = document.createElement("button");
    btn.className = "option";
    btn.textContent = `${letter(i)}. ${label}`;
    if (s.selected === i) btn.classList.add("selected");
    if (s.confirmed) {
      btn.disabled = true;
      if (i === s.answer) btn.classList.add("correct");
      else if (i === s.selected) btn.classList.add("incorrect");
    } else {
      btn.addEventListener("click", () => post("/api/select", { index: i }));
    }
    box.appendChild(btn);
  });

  const fb = $("feedback");
  if (s.confirmed) {
    if (s.correct) {
      fb.textContent = "Correct! 🎉";
      fb.className = "feedback correct";
    } else {
      fb.textContent = `Incorrect — the answer was ${letter(s.answer)}.`;
      fb.className = "feedback incorrect";
    }
  } else {
    fb.textContent = "";
    fb.className = "feedback";
  }

  $("confirmBtn").classList.toggle("hidden", s.confirmed);
  $("confirmBtn").disabled = (s.selected === null);
  $("nextBtn").classList.toggle("hidden", !s.confirmed);
  $("nextBtn").textContent = (s.index + 1 >= s.total) ? "Finish" : "Next Question";
}

$("startBtn").addEventListener("click", () => post("/api/start"));
$("confirmBtn").addEventListener("click", () => post("/api/confirm"));
$("nextBtn").addEventListener("click", () => post("/api/next"));

poll();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        self._send(json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(snapshot())
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}

        if self.path == "/api/start":
            start_quiz()
        elif self.path == "/api/select":
            select_option(data.get("index"))
        elif self.path == "/api/confirm":
            confirm_choice()
        elif self.path == "/api/next":
            next_question()
        else:
            self.send_error(404)
            return

        self._json(snapshot())

    def log_message(self, *args):
        pass  # keep the console clean


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Trivia quiz running at {url}   (Ctrl+C to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
