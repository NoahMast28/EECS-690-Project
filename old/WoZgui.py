# nao_woz_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import json, urllib.request

try:
    import qi
    HAS_QI = True
except ImportError:
    qi = None
    HAS_QI = False

# ---- Global NAO service handles -----------------------------------------
session = None
tts = None
motion = None
posture = None
leds = None

# ---- Quiz server --------------------------------------------------------
SERVER_URL = "http://127.0.0.1:8000"

def _http_get(path):
    try:
        with urllib.request.urlopen(SERVER_URL + path, timeout=1.0) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def _http_post(path, body=None):
    try:
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(
            SERVER_URL + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=1.0) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# ---- NAO control functions ---------------------------------------------
def connect():
    global session, tts, motion, posture, leds
    if not HAS_QI:
        messagebox.showerror("Error", "The 'qi' module (NAOqi SDK) is not installed.\n"
                                      "Quiz controls will still work without it.")
        return
    ip = ip_entry.get().strip()
    if not ip:
        messagebox.showerror("Error", "Please enter the robot IP.")
        return

    status_label.config(text="Connecting...", foreground="orange")
    root.update()

    try:
        session = qi.Session()
        print(f"Connecting to NAO at {ip}:9559...")
        session.connect(f"tcp://{ip}:9559")
        print("Successfully connected to NAO!")
    except RuntimeError as e:
        print(f"Failed to connect to the robot at {ip}: {e}")
        status_label.config(text="Connection failed", foreground="red")
        messagebox.showerror("Connection Error", str(e))
        return

    try:
        tts = session.service("ALTextToSpeech")
        motion = session.service("ALMotion")
        posture = session.service("ALRobotPosture")
        leds = session.service("ALLeds")
    except Exception as e:
        print(f"Failed to load services: {e}")
        status_label.config(text="Service load failed", foreground="red")
        messagebox.showerror("Service Error", str(e))
        return

    motion.wakeUp()
    status_label.config(text="Connected", foreground="green")
    set_nao_actions_enabled(True)

def set_nao_actions_enabled(enabled):
    state = "normal" if enabled else "disabled"
    for w in nao_action_widgets:
        try:
            w.configure(state=state)
        except tk.TclError:
            pass

def say(text):
    if tts:
        tts.say(text)

def say_dynamic():
    text = dyn_entry.get().strip()
    if text:
        say(text)
        dyn_entry.delete(0, tk.END)

def nod():
    if motion:
        motion.angleInterpolation(["HeadPitch"], [[0.2, -0.2, 0.0]],
                                  [[0.5, 1.0, 1.5]], True)

def laugh():
    if tts:
        tts.say("^start(animations/Stand/Emotions/Positive/Laugh_1)")

def led_green():
    if leds:
        leds.fadeRGB("FaceLeds", 0x00FF00, 1.0)

def led_off():
    if leds:
        leds.off("FaceLeds")

def posture_cmd(name):
    if posture:
        posture.goToPosture(name, 0.5)


# ---- Quiz control functions (wizard side) ------------------------------
def quiz_start():
    s = _http_post("/api/start", {})
    if s: apply_quiz_state(s)
    else: quiz_status_var.set("Server unreachable.")

def quiz_select(i):
    s = _http_post("/api/select", {"index": i})
    if s: apply_quiz_state(s)
    else: quiz_status_var.set("Server unreachable.")

def quiz_confirm():
    s = _http_post("/api/confirm", {})
    if s: apply_quiz_state(s)
    else: quiz_status_var.set("Server unreachable.")

def quiz_next():
    s = _http_post("/api/next", {})
    if s: apply_quiz_state(s)
    else: quiz_status_var.set("Server unreachable.")

def apply_quiz_state(s):
    if not s["started"]:
        quiz_q_var.set("Quiz not started.")
        quiz_status_var.set("")
        quiz_start_btn.config(text="Start Quiz")
    elif s["finished"]:
        quiz_q_var.set("Quiz complete.")
        quiz_status_var.set("Finished — press Start to restart.")
        quiz_start_btn.config(text="Restart Quiz")
    else:
        quiz_q_var.set(f"Q{s['index']+1}/{s['total']}: {s['question']}")
        quiz_start_btn.config(text="Restart Quiz")
        if s["confirmed"]:
            if s["correct"]:
                quiz_status_var.set(
                    f"Participant confirmed {chr(65+s['selected'])}: CORRECT ✅")
            else:
                quiz_status_var.set(
                    f"Participant confirmed {chr(65+s['selected'])}: "
                    f"INCORRECT ❌ (answer {chr(65+s['answer'])})")
        elif s["selected"] is not None:
            quiz_status_var.set(
                f"Selected {chr(65+s['selected'])} — awaiting confirm.")
        else:
            quiz_status_var.set("Awaiting participant selection.")

    # Option buttons
    for i, btn in enumerate(option_btns):
        if not s["started"] or s["finished"]:
            btn.config(text=f"{chr(65+i)}. —", state="disabled", bg="#f3f4f6")
            continue
        opt = s["options"][i] if i < len(s["options"]) else "—"
        btn.config(text=f"{chr(65+i)}. {opt}")
        bg = "#f8fafc"
        if s["confirmed"]:
            btn.config(state="disabled")
            if i == s["answer"]:
                bg = "#dcfce7"
            elif i == s["selected"]:
                bg = "#fee2e2"
        else:
            btn.config(state="normal")
            if i == s["selected"]:
                bg = "#e0e7ff"
        btn.config(bg=bg, activebackground=bg)

    # Confirm
    if s["started"] and not s["finished"] and not s["confirmed"] \
            and s["selected"] is not None:
        confirm_btn.config(state="normal")
    else:
        confirm_btn.config(state="disabled")

    # Next
    if s["started"] and not s["finished"] and s["confirmed"]:
        next_btn.config(state="normal",
                        text="Finish" if s["index"]+1 >= s["total"] else "Next Question")
    else:
        next_btn.config(state="disabled")

def poll_server():
    s = _http_get("/api/state")
    if s is not None:
        apply_quiz_state(s)
    root.after(300, poll_server)


# ---- Build the GUI -----------------------------------------------------
root = tk.Tk()
root.title("NAO Wizard-of-Oz GUI")

# Connection frame
conn_frame = ttk.LabelFrame(root, text="Connection", padding=10)
conn_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

ttk.Label(conn_frame, text="Robot IP:").grid(row=0, column=0, padx=5)
ip_entry = ttk.Entry(conn_frame, width=15)
ip_entry.grid(row=0, column=1, padx=5)
connect_btn = ttk.Button(conn_frame, text="Connect", command=connect)
connect_btn.grid(row=0, column=2, padx=5)
status_label = ttk.Label(conn_frame, text="Not connected", foreground="red")
status_label.grid(row=0, column=3, padx=10)

# Pre-scripted speech
speech_frame = ttk.LabelFrame(root, text="Pre-scripted Utterances", padding=10)
speech_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

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
    btn = ttk.Button(speech_frame, text=label, command=lambda t=text: say(t))
    btn.grid(row=i//3, column=i%3, padx=5, pady=3, sticky="ew")

# Dynamic speech
dyn_frame = ttk.LabelFrame(root, text="Dynamic Speech", padding=10)
dyn_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
dyn_entry = ttk.Entry(dyn_frame, width=50)
dyn_entry.grid(row=0, column=0, padx=5, pady=5)
dyn_entry.bind("<Return>", lambda e: say_dynamic())
send_btn = ttk.Button(dyn_frame, text="Send", command=say_dynamic)
send_btn.grid(row=0, column=1, padx=5)

# Social reactions
social_frame = ttk.LabelFrame(root, text="Social Reactions", padding=10)
social_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
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
    btn = ttk.Button(social_frame, text=label, command=cmd)
    btn.grid(row=i//4, column=i%4, padx=5, pady=3, sticky="ew")

# Quiz control (new)
quiz_frame = ttk.LabelFrame(root, text="Quiz Control (Wizard)", padding=10)
quiz_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
for c in range(4):
    quiz_frame.columnconfigure(c, weight=1)

quiz_q_var = tk.StringVar(value="Connecting to quiz server...")
ttk.Label(quiz_frame, textvariable=quiz_q_var,
          font=("TkDefaultFont", 11, "bold")).grid(
    row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

option_btns = []
for i in range(4):
    b = tk.Button(quiz_frame, text=f"{chr(65+i)}. —", anchor="w",
                  relief="groove", bg="#f3f4f6",
                  command=lambda idx=i: quiz_select(idx))
    b.grid(row=1, column=i, padx=4, pady=4, sticky="ew")
    option_btns.append(b)

quiz_status_var = tk.StringVar()
ttk.Label(quiz_frame, textvariable=quiz_status_var,
          foreground="#4f46e5").grid(
    row=2, column=0, columnspan=4, sticky="w", pady=(4, 6))

quiz_start_btn = ttk.Button(quiz_frame, text="Start Quiz", command=quiz_start)
quiz_start_btn.grid(row=3, column=0, padx=4, sticky="ew")
confirm_btn = ttk.Button(quiz_frame, text="Confirm Choice",
                        command=quiz_confirm, state="disabled")
confirm_btn.grid(row=3, column=1, padx=4, sticky="ew")
next_btn = ttk.Button(quiz_frame, text="Next Question",
                     command=quiz_next, state="disabled")
next_btn.grid(row=3, column=2, padx=4, sticky="ew")

ttk.Label(quiz_frame, text=f"Server: {SERVER_URL}",
          foreground="#64748b").grid(
    row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))

# Collect NAO-only widgets so we can disable them pre-connection
nao_action_widgets = []
for child in speech_frame.winfo_children():
    nao_action_widgets.append(child)
for child in dyn_frame.winfo_children():
    nao_action_widgets.append(child)
for child in social_frame.winfo_children():
    nao_action_widgets.append(child)
set_nao_actions_enabled(False)

# Start polling the quiz server
poll_server()

root.mainloop()
