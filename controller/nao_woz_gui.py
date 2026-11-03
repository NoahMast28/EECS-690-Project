import tkinter as tk
from tkinter import ttk, messagebox
import threading, queue, time
import requests

DEFAULT_PROXY = "https://nao-proxy.onrender.com"
DEFAULT_TOKEN = "eQCq7LszQVwEbJgBJV3AEbncZZ-kq-CWjsfoK3fsm-k"

QUESTIONS = [
    {
        "question": "What is the largest US state by land area?",
        "answers": ["Texas", "California", "Alaska", "Montana"],
        "correct": 2,
    },
    {
        "question": 'Which US state is known as the "Sunshine State"?',
        "answers": ["California", "Florida", "Hawaii", "Arizona"],
        "correct": 1,
    },
    {
        "question": "Which US state was the first to ratify the US Constitution?",
        "answers": ["Virginia", "Delaware", "Pennsylvania", "Massachusetts"],
        "correct": 1,
    },
    {
        "question": "How many US states share a land border with Canada?",
        "answers": ["12", "13", "14", "15"],
        "correct": 1,
    },
    {
        "question": "What is the smallest US state by land area?",
        "answers": ["Rhode Island", "Delaware", "Connecticut", "Hawaii"],
        "correct": 0,
    },
]

gui_state = {"screen": "start", "current_question": 0,
             "selected_index": -1, "confirmed": False}

status_queue = queue.Queue()
stop_event = threading.Event()
poller_started = False
proxy_url = ""
auth_token = ""
connected = False


# ---------------- networking ----------------

def _headers():
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def send_command(action, payload=None, target="nao"):
    if not connected:
        messagebox.showerror("Not connected", "Connect to the proxy first.")
        return
    try:
        r = requests.post(
            f"{proxy_url}/api/command",
            headers=_headers(),
            json={"action": action, "payload": payload or {}, "target": target},
            timeout=5,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[ui] send failed: {e}")
        messagebox.showerror("Send error", str(e))


def test_connection():
    global proxy_url, auth_token, connected, poller_started
    proxy_url  = proxy_entry.get().strip().rstrip("/")
    auth_token = token_entry.get().strip()
    if not proxy_url or not auth_token:
        messagebox.showerror("Error", "Proxy URL and token required.")
        return

    status_label.config(text="Connecting...", foreground="orange")
    root.update()

    try:
        r = requests.get(f"{proxy_url}/api/status", headers=_headers(), timeout=5)
        r.raise_for_status()
        connected = True
        if not poller_started:
            poller_started = True
            threading.Thread(target=status_poller, daemon=True).start()
        status_label.config(text="Connected", foreground="green")
        set_actions_enabled(True)
    except Exception as e:
        connected = False
        status_label.config(text=f"Failed: {e}", foreground="red")
        set_actions_enabled(False)


def status_poller():
    while not stop_event.is_set():
        try:
            r = requests.get(f"{proxy_url}/api/status", headers=_headers(), timeout=3)
            if r.ok:
                status_queue.put(("ok", r.json()))
            else:
                status_queue.put(("err", f"HTTP {r.status_code}"))
        except Exception as e:
            status_queue.put(("err", str(e)))
        time.sleep(0.2)


def drain_queue():
    global connected
    try:
        while True:
            kind, payload = status_queue.get_nowait()
            if kind == "ok":
                connected = True
                d = payload
                n_quiz   = d.get("quiz_clients", 0)
                n_bridge = d.get("bridge_clients", 0)
                n_cmds   = d.get("command_count", 0)
                status_label.config(
                    text=f"Connected | quiz={n_quiz} bridge={n_bridge} cmds={n_cmds}",
                    foreground="green" if (n_quiz and n_bridge) else "orange",
                )
                if n_quiz > 0:
                    render_quiz_from_state(d.get("quiz_state", {}))
                else:
                    render_quiz_disconnected()
            else:
                connected = False
                status_label.config(text=f"Proxy error: {payload}", foreground="red")
                set_actions_enabled(False)
                render_quiz_disconnected()
    except queue.Empty:
        pass
    root.after(100, drain_queue)


def set_actions_enabled(enabled):
    state = "normal" if enabled else "disabled"
    for w in action_widgets:
        try: w.configure(state=state)
        except tk.TclError: pass
    if not enabled:
        for btn in answer_buttons:
            btn.config(state="disabled")
        confirm_btn.config(state="disabled")
        next_btn.config(state="disabled")


def on_close():
    stop_event.set()
    root.destroy()


# ---------------- NAO action wrappers ----------------

def say(text):         send_command("say", {"text": text})
def say_dynamic():
    t = dyn_entry.get().strip()
    if t:
        say(t)
        dyn_entry.delete(0, tk.END)
def nod():             send_command("nod")
def laugh():           send_command("laugh")
def led_green():       send_command("led", {"color": "00FF00"})
def led_off():         send_command("led_off")
def posture_cmd(name): send_command("posture", {"name": name})


# ---------------- quiz handlers ----------------

def on_select_answer(i):
    if not connected:
        return
    if gui_state["screen"] != "quiz" or gui_state["confirmed"]:
        return
    send_command("highlight_answer", {"index": i}, target="quiz")


def on_confirm():
    if not connected:
        return
    send_command("advance_question", target="quiz")


def on_next():
    if not connected:
        return
    if gui_state["screen"] == "quiz" and gui_state["confirmed"]:
        send_command("advance_question", target="quiz")


# ---------------- quiz rendering ----------------

def _clear_answers():
    for btn in answer_buttons:
        btn.config(text="", state="disabled", bg="white", fg="black")


def render_quiz_disconnected(msg="Quiz disconnected"):
    progress_label.config(text=msg)
    question_label.config(text="Open the quiz page in a browser to reconnect.")
    _clear_answers()
    confirm_btn.config(state="disabled", text="Confirm")
    next_btn.config(state="disabled", text="Next Question")
    gui_state.update(screen="start", current_question=0,
                     selected_index=-1, confirmed=False)


def render_quiz_start():
    progress_label.config(text="Waiting for quiz to start")
    question_label.config(text="Press Start on the quiz website to begin.")
    _clear_answers()
    confirm_btn.config(state="normal", text="Start Quiz")
    next_btn.config(state="disabled", text="Next Question")
    gui_state.update(screen="start", current_question=0,
                     selected_index=-1, confirmed=False)


def render_quiz_question(cq, si, confirmed):
    if not (0 <= cq < len(QUESTIONS)):
        return
    q = QUESTIONS[cq]
    gui_state.update(screen="quiz", current_question=cq,
                     selected_index=si, confirmed=confirmed)

    progress_label.config(text=f"Question {cq + 1} of {len(QUESTIONS)}")
    question_label.config(text=q["question"])

    for i, btn in enumerate(answer_buttons):
        text = q["answers"][i] if i < len(q["answers"]) else ""
        prefix = "* " if i == q["correct"] else "  "
        btn.config(text=prefix + text)
        if confirmed:
            if i == q["correct"]:
                btn.config(bg="#b6f4b6", fg="black",
                           disabledforeground="black", state="disabled")
            elif i == si:
                btn.config(bg="#ffb6b6", fg="black",
                           disabledforeground="black", state="disabled")
            else:
                btn.config(bg="white", fg="black",
                           disabledforeground="black", state="disabled")
        else:
            btn.config(state="normal", fg="black",
                       bg="#fff3b0" if i == si else "white")

    if confirmed:
        confirm_btn.config(state="disabled", text="Confirm")
        next_btn.config(state="normal",
                        text="See Results" if cq == len(QUESTIONS) - 1
                        else "Next Question")
    else:
        confirm_btn.config(state="normal" if si >= 0 else "disabled",
                           text="Confirm")
        next_btn.config(state="disabled", text="Next Question")


def render_quiz_results(score):
    progress_label.config(text="Quiz complete")
    question_label.config(text=f"Final score: {score}")
    _clear_answers()
    confirm_btn.config(state="disabled", text="Confirm")
    next_btn.config(state="disabled", text="Next Question")
    gui_state.update(screen="results", selected_index=-1, confirmed=True)


def render_quiz_from_state(qs):
    if not isinstance(qs, dict) or not qs:
        render_quiz_disconnected("Waiting for quiz state...")
        return
    screen = qs.get("screen", "start")
    if screen == "start":
        render_quiz_start()
    elif screen == "quiz":
        render_quiz_question(
            qs.get("currentQuestion", 0),
            qs.get("selectedIndex", -1),
            qs.get("confirmed", False),
        )
    elif screen == "results":
        render_quiz_results(qs.get("score", 0))
    else:
        render_quiz_disconnected(f"Unknown screen: {screen}")


# ---------------- GUI layout ----------------

root = tk.Tk()
root.title("NAO WoZ Controller (proxy mode)")
root.protocol("WM_DELETE_WINDOW", on_close)

# Proxy connection
conn = ttk.LabelFrame(root, text="Proxy Connection", padding=10)
conn.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

ttk.Label(conn, text="Proxy URL:").grid(row=0, column=0, sticky="e", padx=4)
proxy_entry = ttk.Entry(conn, width=42)
proxy_entry.insert(0, DEFAULT_PROXY)
proxy_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=4)

ttk.Label(conn, text="Token:").grid(row=1, column=0, sticky="e", padx=4)
token_entry = ttk.Entry(conn, width=42, show="*")
token_entry.insert(0, DEFAULT_TOKEN)
token_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
ttk.Button(conn, text="Connect", command=test_connection).grid(row=1, column=3, padx=4)

status_label = ttk.Label(conn, text="Not connected", foreground="red")
status_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(6, 0))

# Pre-scripted speech
sf = ttk.LabelFrame(root, text="Pre-scripted Utterances", padding=10)
sf.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

prescripts = [
    ("Greeting", "Hello! My name is Nao."),
    ("Intro to Exercise", "We will be doing a Trivia quiz together. We will take turns answering each question. Are you ready?"),
    ("Question 1", "The first thing I am grateful for is this opportunity to interact with you."),
    ("Answering 1", "Now why don't you share something you are grateful for."),
    ("Question 2", "The second thing I am grateful for is the chance to interact with you."),
    ("Answering 2", "What is another thing you are grateful for?"),
    ("Question 3", "The third thing I am grateful for is the technology that lets us talk."),
    ("Answering 3", "Please share one last thing you are grateful for."),
    ("Question 4 (Mistake)", "The third thing I am grateful for is the technology that lets us talk."),
    ("Apologizing (Serious)", "Please share one last thing you are grateful for."),
    ("Apologizing (Humorous)", "Please share one last thing you are grateful for."),
    ("Question 5", "The third thing I am grateful for is the technology that lets us talk."),
    ("Answering 5", "Please share one last thing you are grateful for."),
    ("Conclusion", "Thank you for doing the Trivia quiz with me, I had a lot of fun!"),
]
for i, (label, text) in enumerate(prescripts):
    ttk.Button(sf, text=label, command=lambda t=text: say(t)).grid(
        row=i // 3, column=i % 3, padx=5, pady=3, sticky="ew")

# Dynamic speech
df = ttk.LabelFrame(root, text="Dynamic Speech", padding=10)
df.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
dyn_entry = ttk.Entry(df, width=50)
dyn_entry.grid(row=0, column=0, padx=5, pady=5)
dyn_entry.bind("<Return>", lambda e: say_dynamic())
ttk.Button(df, text="Send", command=say_dynamic).grid(row=0, column=1, padx=5)

# Social reactions
rf = ttk.LabelFrame(root, text="Social Reactions", padding=10)
rf.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
reactions = [
    ("Nod", nod), ("Laugh", laugh),
    ("LED Green", led_green), ("LED Off", led_off),
    ("Stand", lambda: posture_cmd("Stand")),
    ("Sit", lambda: posture_cmd("Sit")),
    ("Crouch", lambda: posture_cmd("Crouch")),
]
for i, (label, cmd) in enumerate(reactions):
    ttk.Button(rf, text=label, command=cmd).grid(
        row=i // 4, column=i % 4, padx=5, pady=3, sticky="ew")

# Quiz control (dynamic)
qf = ttk.LabelFrame(root, text="Quiz Control", padding=10)
qf.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

progress_label = ttk.Label(qf, text="Not connected", foreground="#666",
                           font=("TkDefaultFont", 9, "italic"))
progress_label.grid(row=0, column=0, columnspan=4, sticky="w")

question_label = tk.Label(qf, text="", wraplength=520, justify="left",
                          font=("TkDefaultFont", 11, "bold"), anchor="w")
question_label.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 8))

answer_buttons = []
for i in range(4):
    btn = tk.Button(qf, text="", anchor="w", justify="left",
                    font=("TkFixedFont", 10), relief="raised", bd=1,
                    padx=10, pady=6, bg="white", fg="black",
                    activebackground="#e0e0e0",
                    command=lambda i=i: on_select_answer(i))
    btn.grid(row=2 + i, column=0, columnspan=4, sticky="ew", pady=1)
    answer_buttons.append(btn)

confirm_btn = ttk.Button(qf, text="Confirm", command=on_confirm)
confirm_btn.grid(row=6, column=0, columnspan=2, sticky="ew",
                 padx=(0, 4), pady=(10, 0))
next_btn = ttk.Button(qf, text="Next Question", command=on_next)
next_btn.grid(row=6, column=2, columnspan=2, sticky="ew",
              padx=(4, 0), pady=(10, 0))

# Collect all non-quiz action widgets for enable/disable
action_widgets = []
for frame in (sf, df, rf):
    for child in frame.winfo_children():
        if isinstance(child, (ttk.Button, tk.Button)):
            action_widgets.append(child)
set_actions_enabled(False)

root.after(100, drain_queue)
root.mainloop()
