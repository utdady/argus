const transcript = document.getElementById("transcript");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const pttBtn = document.getElementById("ptt");
const meta = document.getElementById("meta");
const confirmBar = document.getElementById("confirmBar");
const confirmText = document.getElementById("confirmText");
const btnYes = document.getElementById("btnYes");
const btnNo = document.getElementById("btnNo");

let sessionId = localStorage.getItem("argus_session_id") || null;
let confirmToken = null;
let busy = false;
let voiceEnabled = false;
let mediaStream = null;
let mediaRecorder = null;
let recordChunks = [];

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
  if (voiceEnabled) pttBtn.disabled = v;
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

function playAudioBase64(b64, mime) {
  if (!b64) return;
  const audio = new Audio(`data:${mime || "audio/wav"};base64,${b64}`);
  audio.play().catch(() => {});
}

function handleTurn(data, { transcriptText } = {}) {
  if (transcriptText) addBubble("you", transcriptText, "voice");
  addBubble("argus", data.reply, data.status);
  if (data.audio_base64) playAudioBase64(data.audio_base64, data.audio_mime);
  if (data.status === "awaiting_confirm") showConfirm(data);
  else hideConfirm();
}

async function postVoice(blob) {
  const sid = await ensureSession();
  const body = new FormData();
  body.append("session_id", sid);
  body.append("audio", blob, "ptt.webm");
  const res = await fetch("/api/voice", { method: "POST", body });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Voice failed");
  sessionId = data.session_id;
  localStorage.setItem("argus_session_id", sessionId);
  return data;
}

async function startRecording() {
  if (busy || !voiceEnabled) return;
  recordChunks = [];
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : "audio/webm";
  mediaRecorder = new MediaRecorder(mediaStream, { mimeType: mime });
  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordChunks.push(e.data);
  };
  mediaRecorder.start();
  pttBtn.classList.add("recording");
  pttBtn.textContent = "Release…";
}

async function stopRecording() {
  if (!mediaRecorder) return;
  const recorder = mediaRecorder;
  mediaRecorder = null;
  await new Promise((resolve) => {
    recorder.onstop = resolve;
    recorder.stop();
  });
  (mediaStream?.getTracks() || []).forEach((t) => t.stop());
  mediaStream = null;
  pttBtn.classList.remove("recording");
  pttBtn.textContent = "Hold to talk";

  const blob = new Blob(recordChunks, { type: recorder.mimeType || "audio/webm" });
  recordChunks = [];
  if (!blob.size) return;

  setBusy(true);
  try {
    const data = await postVoice(blob);
    handleTurn(data, { transcriptText: data.transcript });
  } catch (err) {
    addBubble("argus", String(err.message || err), "error");
  } finally {
    setBusy(false);
  }
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

pttBtn.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  startRecording().catch((err) => {
    addBubble("argus", String(err.message || err), "error");
  });
});
pttBtn.addEventListener("pointerup", () => {
  stopRecording().catch((err) => {
    addBubble("argus", String(err.message || err), "error");
  });
});
pttBtn.addEventListener("pointerleave", () => {
  if (mediaRecorder) stopRecording().catch(() => {});
});
pttBtn.addEventListener("pointercancel", () => {
  if (mediaRecorder) stopRecording().catch(() => {});
});

(async () => {
  try {
    const health = await fetch("/api/health").then((r) => r.json());
    await ensureSession();
    voiceEnabled = !!health.voice_enabled;
    pttBtn.disabled = !voiceEnabled;
    meta.textContent = voiceEnabled
      ? `${health.model} · voice on`
      : `${health.model} · text only`;
  } catch {
    meta.textContent = "offline";
  }
  input.focus();
})();
