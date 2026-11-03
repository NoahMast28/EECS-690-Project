(function () {
  // ==== CONFIG ====
  const PROXY_URL = "https://nao-proxy.onrender.com".replace(/\/+$/, "");
  const TOKEN     = "eQCq7LszQVwEbJgBJV3AEbncZZ-kq-CWjsfoK3fsm-k";
  // ================

  let socket = null;
  let reconnectDelay = 1000;
  let lastStateJson = "";

  function syncState() {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    if (!window.quiz) return;
    const s = window.quiz.getState();
    const payload = {
      screen: s.screen,
      currentQuestion: s.currentQuestion,
      selectedIndex: s.selectedIndex,
      confirmed: s.confirmed,
      score: s.score,
    };
    const json = JSON.stringify(payload);
    if (json !== lastStateJson) {
      lastStateJson = json;
      socket.send(JSON.stringify({ type: "state", state: payload }));
    }
  }
  setInterval(syncState, 300);

  function connect() {
    const wsBase = PROXY_URL.replace(/^https:\/\//, "wss://")
                            .replace(/^http:\/\//, "ws://");
    const url = `${wsBase}/ws/quiz?token=${encodeURIComponent(TOKEN)}`;
    socket = new WebSocket(url);

    socket.onopen = () => {
      console.log("[woz] connected to proxy");
      reconnectDelay = 1000;
      showBadge("woz: connected", "#0a0");
      lastStateJson = "";          // force a fresh send on reconnect
      setTimeout(syncState, 50);
    };

    socket.onmessage = (event) => {
      try { handleCommand(JSON.parse(event.data)); }
      catch (e) { console.error("[woz] bad message", e); }
    };

    socket.onclose = () => {
      showBadge("woz: reconnecting...", "#a80");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    socket.onerror = (err) => console.error("[woz] socket error", err);
  }

  function handleCommand(cmd) {
    const { action, payload = {} } = cmd;
    console.log("[woz] <-", action, payload);

    if (!window.quiz) {
      console.warn("[woz] quiz API not ready");
      return;
    }

    switch (action) {
      // Select / highlight an answer. Mutually exclusive with the user's
      // own click — one shared `selectedIndex` lives in the quiz state.
      case "highlight_answer":
      case "auto_answer":
        window.quiz.selectAnswer(payload.index);
        break;

      // Highlight the correct answer for the current question (yellow).
      // Does not confirm — the user still has to click Confirm.
      case "reveal_answer": {
        const s = window.quiz.getState();
        const cur = s.questions[s.currentQuestion];
        if (cur && s.screen === "quiz" && !s.confirmed) {
          window.quiz.selectAnswer(cur.correct);
        }
        break;
      }

      // Advance: Start → Confirm → Next → See Results → Restart.
      // If nothing is selected yet, Confirm is a no-op.
      case "advance_question":
        window.quiz.advance();
        break;

      case "show_text":
        showOverlay(payload.text || "", payload.duration_ms || 3000);
        break;

      default:
        console.warn("[woz] unknown action", action);
    }
  }

  function showOverlay(text, ms) {
    let el = document.getElementById("woz-overlay");
    if (!el) {
      el = document.createElement("div");
      el.id = "woz-overlay";
      el.style.cssText =
        "position:fixed;bottom:16px;right:16px;background:rgba(0,0,0,.8);color:#fff;" +
        "padding:8px 14px;border-radius:8px;font:13px monospace;z-index:99999;" +
        "max-width:400px;";
      document.body.appendChild(el);
    }
    el.textContent = text;
    clearTimeout(el._t);
    el._t = setTimeout(() => el.remove(), ms);
  }

  function showBadge(text, color) {
    let el = document.getElementById("woz-badge");
    if (!el) {
      el = document.createElement("div");
      el.id = "woz-badge";
      el.style.cssText =
        "position:fixed;top:8px;left:8px;padding:4px 10px;border-radius:12px;" +
        "font:11px monospace;color:#fff;z-index:99999;transition:opacity .3s;";
      document.body.appendChild(el);
    }
    el.textContent = text;
    el.style.background = color;
  }

  window.woz = { handleCommand, connect };
  connect();
})();