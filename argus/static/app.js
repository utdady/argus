const transcript = document.getElementById("transcript");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const meta = document.getElementById("meta");
const confirmBar = document.getElementById("confirmBar");
const confirmText = document.getElementById("confirmText");
const btnYes = document.getElementById("btnYes");
const btnNo = document.getElementById("btnNo");

let sessionId = localStorage.getItem("argus_session_id") || null;
let confirmToken = null;
let busy = false;

function addBubble(role, text, status) {
  const el = document.createElement("div");
  el.className = `bubble ${role === "you" ? "you" : "argus"}`;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "you" ? "You" : "Argus";
  el.appendChild(who);
  el.appendChild(document.createTextNode(text));
  if (status) {
    const st = document.createElement("div");
    st.className = "status";
    st.textContent = status;
    el.appendChild(st);
  }
  transcript.appendChild(el);
  transcript.scrollTop = transcript.scrollHeight;
}

function setBusy(v) {
  busy = v;
  sendBtn.disabled = v;
  btnYes.disabled = v;
  btnNo.disabled = v;
  input.disabled = v;
}

function showConfirm(data) {
  confirmToken = data.confirm_token;
  const args = data.pending_args ? JSON.stringify(data.pending_args) : "";
  confirmText.textContent = `Confirm ${data.pending_tool || "action"} ${args}`.trim();
  confirmBar.classList.remove("hidden");
}

function hideConfirm() {
  confirmToken = null;
  confirmBar.classList.add("hidden");
}

async function ensureSession() {
  if (sessionId) return sessionId;
  const res = await fetch("/api/sessions", { method: "POST" });
  if (!res.ok) throw new Error("Failed to create session");
  const data = await res.json();
  sessionId = data.session_id;
  localStorage.setItem("argus_session_id", sessionId);
  return sessionId;
}

async function postChat(message) {
  const sid = await ensureSession();
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sid, message }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Chat failed");
  sessionId = data.session_id;
  localStorage.setItem("argus_session_id", sessionId);
  return data;
}

async function postConfirm(approved) {
  const res = await fetch("/api/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      approved,
      token: confirmToken,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Confirm failed");
  return data;
}

function handleTurn(data) {
  addBubble("argus", data.reply, data.status);
  if (data.status === "awaiting_confirm") showConfirm(data);
  else hideConfirm();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message || busy) return;
  input.value = "";
  addBubble("you", message);
  setBusy(true);
  try {
    const data = await postChat(message);
    handleTurn(data);
  } catch (err) {
    addBubble("argus", String(err.message || err), "error");
  } finally {
    setBusy(false);
    input.focus();
  }
});

btnYes.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true);
  try {
    const data = await postConfirm(true);
    handleTurn(data);
  } catch (err) {
    addBubble("argus", String(err.message || err), "error");
  } finally {
    setBusy(false);
  }
});

btnNo.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true);
  try {
    const data = await postConfirm(false);
    handleTurn(data);
  } catch (err) {
    addBubble("argus", String(err.message || err), "error");
  } finally {
    setBusy(false);
  }
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

(async () => {
  try {
    const health = await fetch("/api/health").then((r) => r.json());
    await ensureSession();
    meta.textContent = `${health.model} · local`;
  } catch {
    meta.textContent = "offline";
  }
  input.focus();
})();
