(function () {
  // ==== CONFIG ====
  const PROXY_URL = "wss://your-proxy.onrender.com";
  const TOKEN     = "change-me-in-production";
  // ================

  let socket = null;
  let reconnectDelay = 1000;

  function connect() {
    const url = `${PROXY_URL.replace("https://", "wss://")}/ws/quiz?token=${TOKEN}`;
    socket = new WebSocket(url);

    socket.onopen = () => {
      console.log("[woz] connected to proxy");
      reconnectDelay = 1000;
      showBadge("woz: connected", "#0a0");
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

    switch (action) {
      case "highlight_answer":
        highlightAnswer(payload.index);
        break;
      case "reveal_answer":
        revealCorrect(payload.question_id);
        break;
      case "advance_question":
        document.querySelector(".next-question")?.click();
        break;
      case "auto_answer":
        autoAnswer(payload.question_id, payload.index);
        break;
      case "show_text":
        showOverlay(payload.text || "", payload.duration_ms || 3000);
        break;
      default:
        console.warn("[woz] unknown action", action);
    }
  }

  // ---- Replace these with your quiz's actual DOM hooks ----
  function highlightAnswer(i) {
    document.querySelectorAll(".answer").forEach((el, idx) => {
      el.classList.toggle("woz-highlight", idx === i);
    });
  }

  function revealCorrect(questionId) {
    const q = document.querySelector(`[data-question-id="${questionId}"]`);
    if (!q) return;
    q.querySelectorAll(".answer").forEach(el => {
      if (el.dataset.correct === "true") el.classList.add("woz-reveal-correct");
    });
  }

  function autoAnswer(questionId, index) {
    const q = document.querySelector(`[data-question-id="${questionId}"]`);
    if (!q) return;
    const answers = q.querySelectorAll(".answer");
    answers[index]?.click();
  }

  function showOverlay(text, ms) {
    let el = document.getElementById("woz-overlay");
    if (!el) {
      el = document.createElement("div");
      el.id = "woz-overlay";
      el.style.cssText =
        "position:fixed;bottom:16px;right:16px;background:rgba(0,0,0,.8);color:#fff;" +
        "padding:8px 14px;border-radius:8px;font:13px monospace;z-index:99999;max-width:400px;";
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