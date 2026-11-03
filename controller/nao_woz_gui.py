"""
NAO WoZ Controller (proxy mode) - runs on PC 2.
Sends commands to the proxy server, which relays them to the NAO bridge / quiz page.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, queue, time
import requests

DEFAULT_PROXY = "https://your-proxy.onrender.com"
DEFAULT_TOKEN = "change-me-in-production"

status_queue     = queue.Queue()
stop_event       = threading.Event()
poller_started   = False
proxy_url        = ""
auth_token       = ""
connected        = False


# ---------- networking ----------
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
    global proxy_url, auth_token, connected
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
        d = r.json()
        connected = True
        status_label.config(
            text=f"Connected | quiz={d['quiz_clients']} bridge={d['bridge_clients']}",
            foreground="green",
        )
        set_actions_enabled(True)
        global poller_started
        if not poller_started:
            poller_started = True
            threading.Thread(target=status_poller, daemon=True).start()
    except Exception as e:
        connected = False
        status_label.config(text=f"Failed: {e}", foreground="red")
        set_actions_enabled(False)


def status_poller():
    while not stop_event.is_set():
        if not connected:
            time.sleep(1); continue
        try:
            r = requests.get(f"{proxy_url}/api/status", headers=_headers(), timeout=3)
            if r.ok:
                d = r.json()
                status_queue.put(("ok",
                    f"Connected | quiz={d['quiz_clients']} "
                    f"bridge={d['bridge_clients']} cmds={d['command_count']}"))
            else:
                status_queue.put(("err", f"HTTP {r.status_code}"))
        except Exception as e:
            status_queue.put(("err", str(e)))
        time.sleep(2)


def drain_queue():
    global connected
    try:
        while True:
            kind, msg = status_queue.get_nowait()
            if kind == "ok":
                status_label.config(text=msg, foreground="green")
            else:
                connected = False
                status_label.config(text=f"Proxy error: {msg}", foreground="red")
                set_actions_enabled(False)
    except queue.Empty:
        pass
    root.after(250, drain_queue)


def set_actions_enabled(enabled):
    state = "normal" if enabled else "disabled"
    for w in action_widgets:
        try: w.configure(state=state)
        except tk.TclError: pass


def on_close():
    stop_event.set()
    root.destroy()


# ---------- action wrappers ----------
def say(text):         send_command("say", {"text": text})
def say_dynamic():
    t = dyn_entry.get().strip()
    if t: say(t); dyn_entry.delete(0, tk.END)
def nod():             send_command("nod")
def laugh():           send_command("laugh")
def led_green():       send_command("led", {"color": "00FF00"})
def led_off():         send_command("led_off")
def posture_cmd(name): send_command("posture", {"name": name})

def quiz_highlight():
    try: idx = int(quiz_index_entry.get())
    except ValueError: return messagebox.showerror("Error", "index must be integer")
    send_command("highlight_answer", {"index": idx}, target="quiz")

def quiz_reveal():
    try: qid = int(quiz_qid_entry.get())
    except ValueError: return messagebox.showerror("Error", "question id must be integer")
    send_command("reveal_answer", {"question_id": qid}, target="quiz")

def quiz_advance():
    send_command("advance_question", target="quiz")

def quiz_auto_answer():
    try: qid = int(quiz_qid_entry.get()); idx = int(quiz_index_entry.get())
    except ValueError: return messagebox.showerror("Error", "qid and index must be ints")
    send_command("auto_answer", {"question_id": qid, "index": idx}, target="quiz")


# ---------- GUI ----------
root = tk.Tk()
root.title("NAO WoZ Controller (proxy mode)")
root.protocol("WM_DELETE_WINDOW", on_close)

# connection frame
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

# pre-scripted speech
sf = ttk.LabelFrame(root, text="Pre-scripted Utterances", padding=10)
sf.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

prescripts = [
    ("Greeting", "Hello! My name is Nao."),
    ("Intro to Exercise", "Today, we will do the Three Good Things exercise. So we will take turns sharing three things that we are grateful for."),
    ("Robot Gratitude 1", "The first thing I am grateful for is this opportunity to interact with you."),
    ("Prompt 1", "Now why don't you share something you are grateful for."),
    ("Robot Gratitude 2", "The second thing I am grateful for is the chance to interact with you."),
    ("Prompt 2", "What is another thing you are grateful for?"),
    ("Robot Gratitude 3", "The third thing I am grateful for is the technology that lets us talk."),
    ("Prompt 3", "Please share one last thing you are grateful for."),
    ("Conclusion", "Thank you for participating. Remember to focus on the good things. Goodbye!"),
]
for i, (label, text) in enumerate(prescripts):
    b = ttk.Button(sf, text=label, command=lambda t=text: say(t))
    b.grid(row=i // 3, column=i % 3, padx=5, pady=3, sticky="ew")

# dynamic speech
df = ttk.LabelFrame(root, text="Dynamic Speech", padding=10)
df.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
dyn_entry = ttk.Entry(df, width=50)
dyn_entry.grid(row=0, column=0, padx=5, pady=5)
dyn_entry.bind("<Return>", lambda e: say_dynamic())
ttk.Button(df, text="Send", command=say_dynamic).grid(row=0, column=1, padx=5)

# social reactions
rf = ttk.LabelFrame(root, text="Social Reactions", padding=10)
rf.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
reactions = [
    ("Nod", nod),
    ("Laugh", laugh),
    ("LED Green", led_green),
    ("LED Off", led_off),
    ("Stand", lambda: posture_cmd("Stand")),
    ("Sit", lambda: posture_cmd("Sit")),
    ("Crouch", lambda: posture_cmd("Crouch")),
]
for i, (label, cmd) in enumerate(reactions):
    ttk.Button(rf, text=label, command=cmd).grid(
        row=i // 4, column=i % 4, padx=5, pady=3, sticky="ew")

# quiz control
qf = ttk.LabelFrame(root, text="Quiz Control", padding=10)
qf.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

ttk.Label(qf, text="Q-ID:").grid(row=0, column=0, padx=4)
quiz_qid_entry = ttk.Entry(qf, width=6)
quiz_qid_entry.insert(0, "1")
quiz_qid_entry.grid(row=0, column=1, padx=4)

ttk.Label(qf, text="Answer idx:").grid(row=0, column=2, padx=4)
quiz_index_entry = ttk.Entry(qf, width=6)
quiz_index_entry.insert(0, "0")
quiz_index_entry.grid(row=0, column=3, padx=4)

ttk.Button(qf, text="Highlight",   command=quiz_highlight).grid(row=0, column=4, padx=4)
ttk.Button(qf, text="Reveal",      command=quiz_reveal).grid(row=0, column=5, padx=4)
ttk.Button(qf, text="Next Q",      command=quiz_advance).grid(row=0, column=6, padx=4)
ttk.Button(qf, text="Auto-Answer", command=quiz_auto_answer).grid(row=0, column=7, padx=4)

# collect action widgets
action_widgets = []
for frame in (sf, df, rf, qf):
    for child in frame.winfo_children():
        if isinstance(child, ttk.Button) and child is not None:
            action_widgets.append(child)
set_actions_enabled(False)

root.after(250, drain_queue)
root.mainloop()