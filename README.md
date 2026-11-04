# NAO Wizard-of-Oz Trivia System

A three-part remote-control system that lets an operator secretly guide a NAO robot and a web-based trivia quiz in real time, without the quiz participant knowing.

### Architecture

All traffic flows through a cloud proxy:

- **Proxy server** (`proxy/proxy_server.py`, deployed on Render) — a Flask app that relays JSON commands between the operator and the quiz/bridge via HTTPS POST and WebSockets. It holds the most recent quiz state so the operator can see what the participant is doing, and it authenticates every request with a shared Bearer token.

- **NAO bridge** (`bridge/nao_bridge.py`, runs on the robot's LAN) — connects to the proxy over a WebSocket and translates incoming commands (`say`, `nod`, `led`, `posture`, etc.) into NAOqi API calls on the robot.

- **Operator GUI** (`controller/nao_woz_gui.py`, Tkinter) — the operator's control panel. Sends pre-scripted or free-typed speech to the robot, triggers built-in gestures (nod, shake head, wave, shrug, laugh), controls face LEDs and posture, and mirrors the quiz in real time: shows the current question and answer options (correct one starred), highlights selections, confirms answers, and advances questions — all in sync with what the participant sees.

- **Quiz web page** (`quiz/quiz_demo.html` + `quiz/quiz_integration.js`) — a self-contained five-question US-states trivia quiz with start screen, one-question-at-a-time layout, answer selection, confirm/next flow, scoring (+100/−100), and a final results screen. A small integration script opens a WebSocket to the proxy, reports its current state on every change, and applies incoming operator commands (highlight, confirm, advance, reveal) to the live DOM.

### Data flow

Operator clicks → GUI POSTs command to proxy → proxy broadcasts to the right client(s) → NAO speaks/gestures, and/or the quiz page updates.

In the reverse direction, the quiz page pushes its state to the proxy every 300 ms, and the GUI polls `/api/status` every 200 ms to render an exact mirror of the participant's screen.

### Result

A low-latency WoZ setup where the operator can drive both a physical robot and a live web quiz from a single window, on separate machines, over the public internet, without touching the quiz participant's machine or the school's hosting.

# Brief Demonstration Video

[![Watch the video](https://youtube.com/shorts/pouMCTpRlOM?feature=share)](https://youtube.com/shorts/pouMCTpRlOM?feature=share)

# NAO Wizard-of-Oz Demo — Setup Guide

This guide covers the two machines that drive the live demo:

- **PC 1** Lab machine — runs the **bridge** (talks to the NAO robot) and shows the **quiz** in a browser. This is the PC used by the participant.
- **PC 2** WoZ Operator — runs the **Tkinter controller** that sends commands to the robot and the quiz. This is the PC used by the operator.

The cloud proxy at `https://nao-proxy.onrender.com` relays everything between them. It is already deployed — no setup needed for the proxy itself.

---

## Repository layout

```
nao-woz/
├── proxy/          # deployed to Render (no action needed)
├── bridge/         # runs on PC 1
├── controller/     # runs on PC 2
└── quiz/           # uploaded to school web hosting (already done)
```

---

## Configuration values (used throughout this guide)

```
PROXY_URL   = https://nao-proxy.onrender.com
PROXY_TOKEN = Ask for this value from Noah
NAO_IP      = 10.117.35.236
QUIZ_URL    = https://people.eecs.ku.edu/~n882m961
```

Note: The current NAO IP is for Nao #1 (Tars). The NAO assigned to us was not turning on when I was testing it despite it seemingly being charged. We might change this IP in the future.

---

## Startup order

Always bring things up in this order. Each step tells you how to verify before moving on.

1. Wake the proxy.
2. Start the bridge on PC 1.
3. Open the quiz on PC 1.
4. Launch and connect the controller on PC 2.
5. Start the quiz.

---

## Step 1 — Wake the proxy (any machine)

The proxy is on Render's free tier and sleeps after ~15 minutes idle. Cold start takes 30–60 seconds.

Open the following URL in a browser:

```
https://nao-proxy.onrender.com/
```

Wait until the page returns JSON. When it looks like this, the proxy is awake:

```json
{"status": "ok", "quiz_clients": 0, "bridge_clients": 0}
```

---

## Step 2 — Start the bridge on PC 1 (Lab Machine)

### One-time setup

```bash
git clone https://github.com/NoahMast28/EECS-690-Project.git
cd EECS-690-Project
python3 -m pip install -r bridge/requirements.txt
```

Qi should already be installed on the lab machine. However, you can confirm it with this command:

```bash
python3 -c "import qi; print('qi OK')"
```

### Each session

Set the three environment variables and start the bridge:

```bash
cd EECS-690-Project
export PROXY_URL="https://nao-proxy.onrender.com"
export PROXY_TOKEN="{PROXY_TOKEN}"
export NAO_IP="10.117.35.236"
python3 bridge/nao_bridge.py
```

### Verify

The bridge terminal should print:

```
[bridge] connecting to NAO at 10.117.35.236:9559 ...
[bridge] NAO ready
[bridge] connected to proxy wss://nao-proxy.onrender.com/ws/bridge?token=...
```

Leave this terminal running in the background.

Now check the proxy:

```
https://nao-proxy.onrender.com/
```

You should see:

```json
{"status": "ok", "quiz_clients": 0, "bridge_clients": 1}
```

## Step 3 — Open the quiz on PC 1

In a browser on PC 1, go the the quiz hosted on my student website:

[https://<your-school-url>/quiz_demo.html](https://people.eecs.ku.edu/~n882m961/quiz_demo.html)

You should see a green **`woz: connected`** badge appears in the top-left of the page. This will probably be changed to something like `nao: connected` in the future to prevent the participant from knowing NAO is WoZ controlled.

The proxy should show a connected quiz client now:

```json
{"status": "ok", "quiz_clients": 1, "bridge_clients": 1}
```

---

## Step 4 — Launch the controller on PC 2 (WoZ Operator)

### One-time setup

Ensure Tkinter is installed on your machine.

For Ubuntu:
```bash
sudo apt install python3-tk
```

For Arch:
```bash
sudo pacman -S tk
```

Next, verify its installed:
```bash
python3 -c "import tkinter; print('tk OK')"
```

Then clone the repo and install requirements:

```bash
git clone https://github.com/NoahMast28/EECS-690-Project.git
cd EECS-690-Project
python3 -m pip install -r controller/requirements.txt
```

> If you ever run the controller on Ubuntu instead, the Tkinter package is `python3-tk` (`sudo apt install python3-tk`).

### Each session

```bash
cd nao-woz
python3 controller/nao_woz_gui.py
```

The window opens with all action buttons **disabled**. In the **Proxy Connection** frame, enter:

- **Proxy URL:** `https://nao-proxy.onrender.com`
- **Token:** `{PROXY_TOKEN}`

Click **Connect**. The status label should turn green. And you should see a start quiz option.

---
