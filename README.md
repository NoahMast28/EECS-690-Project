# NAO Wizard-of-Oz Demo — Setup Guide

This guide covers the two machines that drive the live demo:

- **PC 1** (Ubuntu) — runs the **bridge** (talks to the NAO robot) and shows the **quiz** in a browser.
- **PC 2** (Arch) — runs the **Tkinter controller** that sends commands to the robot and the quiz.

The cloud proxy at `https://nao-proxy.onrender.com` relays everything between them. It is already deployed — no setup needed for the proxy itself.

---

## Repository layout

```
nao-woz/
├── proxy/          # deployed to Render (no action needed)
├── bridge/         # runs on PC 1 (Ubuntu)
├── controller/     # runs on PC 2 (Arch)
└── quiz/           # uploaded to school web hosting (already done)
```

Replace `<you>` in the clone commands below with your GitHub username.

---

## Configuration values (used throughout this guide)

```
PROXY_URL   = https://nao-proxy.onrender.com
PROXY_TOKEN = Ask for this value from Noah
NAO_IP      = 10.117.35.236
QUIZ_URL    = https://people.eecs.ku.edu/~n882m961
```

---

## Startup order

Always bring things up in this order. Each step tells you how to verify before moving on.

1. Wake the proxy.
2. Start the bridge on PC 1.
3. Open the quiz on PC 1.
4. Launch and connect the controller on PC 2.
5. Run the smoke test.

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

> If it takes a long time, that's normal — it's waking up. Keep refreshing until you see the JSON.

---

## Step 2 — Start the bridge on PC 1 (Ubuntu)

### One-time setup

```bash
git clone https://github.com/<you>/nao-woz.git
cd nao-woz
python3 -m pip install -r bridge/requirements.txt
```

Confirm `qi` is installed (the SoftBank NAOqi SDK — **not** the PyPI `qi` package):

```bash
python3 -c "import qi; print('qi OK')"
```

If this fails, use the Python interpreter your lab originally configured for NAOqi. Do **not** `pip install qi`.

### Each session

Set the three environment variables and start the bridge:

```bash
cd nao-woz
export PROXY_URL="https://nao-proxy.onrender.com"
export PROXY_TOKEN="Same token value as defined earlier"
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

Leave this terminal running.

Now check the proxy:

```
https://nao-proxy.onrender.com/
```

You should see:

```json
{"status": "ok", "quiz_clients": 0, "bridge_clients": 1}
```

**`bridge_clients: 1` means PC 1's bridge is live.** If it's still `0`:
- Wait 60 seconds (Render cold start) and refresh.
- Token typo → the WebSocket closes silently. Re-copy `PROXY_TOKEN`.
- Network block → run `curl https://nao-proxy.onrender.com/` from PC 1; if that fails, outbound HTTPS is blocked.

---

## Step 3 — Open the quiz on PC 1

In a browser on PC 1, navigate to your school-hosted quiz page:

```
https://<your-school-url>/quiz_demo.html
```

Press **F12** to open DevTools → **Console**. You should see:

```
[woz] connected to proxy
```

And a green **`woz: connected`** badge appears in the top-left of the page.

Now check the proxy again:

```
https://nao-proxy.onrender.com/
```

You should see:

```json
{"status": "ok", "quiz_clients": 1, "bridge_clients": 1}
```

**Both numbers non-zero = PC 1 is fully wired up.**

> Keep this browser tab open for the whole session. Closing it drops `quiz_clients` back to 0.
>
> If the badge stays `woz: reconnecting`:
> - DevTools → Network → **WS** filter → check the Request URL. It must be `wss://nao-proxy.onrender.com/ws/quiz?token=...` with a **single slash** after the host.
> - DevTools → Console → look for the error. `401` = wrong token in `quiz_integration.js`; mixed-content warning = `PROXY_URL` is `http://` not `https://`.
> - View the served JS (`https://<your-school-url>/quiz_integration.js`) and confirm `PROXY_URL` and `TOKEN` match the values at the top of this guide.

---

## Step 4 — Launch the controller on PC 2 (Arch)

### One-time setup

Tkinter on Arch lives in the `tk` package:

```bash
sudo pacman -S tk
python3 -c "import tkinter; print('tk OK')"
```

Then clone and install:

```bash
git clone https://github.com/<you>/nao-woz.git
cd nao-woz
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
- **Token:** `Ask Noah for this value`

Click **Connect**. The status label turns green within ~1 second:

```
Connected | quiz=1 bridge=1 cmds=0
```

The buttons become enabled.

> If it goes red:
> - `401` → token typo
> - `404` → wrong URL (should end at the host, no path)
> - Timeout → proxy is asleep; go back to Step 1

---

## Step 5 — Smoke test

Run these in order. Each verifies one path of the system.

### A. Quiz path (PC 2 → proxy → PC 1 browser)

In the **Quiz Control** frame, use these values against the demo quiz:

| Action | Q-ID | Answer idx | Expected result on PC 1 |
|---|---|---|---|
| **Highlight** | `1` | `0` | First answer of Q1 turns yellow |
| **Highlight** | `1` | `2` | Third answer turns yellow, first clears |
| **Reveal** | `1` | — | Q1 correct answer ("My friends") turns green |
| **Reveal** | `2` | — | Q2 correct answer ("Daily") turns green |
| **Auto-Answer** | `2` | `2` | Third answer of Q2 is clicked |

PC 1's DevTools Console should log `[woz] <- highlight_answer {index: 0}` etc. for each. PC 2's status label's `cmds=N` counter increments after every click.

### B. Robot path (PC 2 → proxy → PC 1 bridge → NAO)

| Action on PC 2 | Expected on the robot |
|---|---|
| **Greeting** | NAO says "Hello! My name is Nao." |
| **Dynamic Speech** → type text → Enter | NAO says that text |
| **Nod** | NAO nods its head |
| **LED Green** | Face LEDs turn green |
| **LED Off** | Face LEDs turn off |
| **Stand** | Robot stands |

The bridge terminal on PC 1 logs `[bridge] <- #N say {...}` for each command.

### C. Combined (the real scenario)

1. Click **Greeting** → NAO introduces itself.
2. Q-ID `1`, Answer idx `1`, click **Auto-Answer** → quiz selects the correct Q1 answer.
3. Q-ID `1`, click **Reveal** → quiz highlights it green.
4. Click **Nod** → NAO nods.
5. Click **Prompt 1** → NAO says "Now why don't you share something you are grateful for."

If all three pass, the system is ready.

---

## Before every session — quick checklist

- [ ] Open `https://nao-proxy.onrender.com/` and wait for the JSON (wakes the proxy)
- [ ] PC 1: `python3 bridge/nao_bridge.py` running, terminal shows `[bridge] connected to proxy`
- [ ] `https://nao-proxy.onrender.com/` shows `bridge_clients: 1`
- [ ] PC 1: quiz tab open, green `woz: connected` badge
- [ ] `https://nao-proxy.onrender.com/` shows `quiz_clients: 1` and `bridge_clients: 1`
- [ ] PC 2: controller open, clicked **Connect**, status shows `quiz=1 bridge=1`
- [ ] Warm-up: one **Greeting** (robot) and one **Highlight** (quiz)

---

## Troubleshooting summary

| Symptom | Check |
|---|---|
| `quiz_clients` stays `0` | Quiz tab open? Green `woz: connected` badge? Check DevTools → Network → WS request URL for `//ws/quiz` (double slash) or `ws://` (should be `wss://`). |
| `bridge_clients` stays `0` | Bridge terminal running on PC 1? Any `[bridge] reconnecting in 5s ...` lines = token mismatch. |
| Controller status is red | Wrong URL/token, or proxy is asleep — open the proxy root URL to wake it, retry. |
| Quiz reacts, robot doesn't | `[bridge]` terminal shows the command but a Python traceback follows → NAOqi call failed. No log line at all → bridge disconnected. |
| Robot reacts, quiz doesn't | Check PC 1 Console for `[woz] <- ...`. If it logs but nothing highlights, the DOM selectors in `quiz_integration.js` don't match the page. |
| Everything is slow | Render free tier. Warm up with one command before starting the real session. |

---

## Operational notes

- **Keep the quiz tab open.** Closing it drops `quiz_clients` to 0 and quiz commands are silently ignored.
- **The proxy sleeps after ~15 minutes of inactivity.** If you pause for a while, do Step 1 again and click **Connect** on PC 2. The bridge reconnects on its own; the controller does not.
- **Do not `pip install qi`.** The PyPI `qi` package is unrelated to SoftBank's NAOqi SDK and will break the bridge. Only the SoftBank installer provides the working `qi`.
- **Rotating the token.** If `PROXY_TOKEN` is ever exposed or you want a fresh one, change it in Render → Environment, then update it in three places: `quiz/quiz_integration.js` (on the school site), the controller's Token field, and the `export PROXY_TOKEN=...` line in Step 2.
