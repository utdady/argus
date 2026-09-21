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
let capturing = false;
let captureStartedAt = 0;
let spaceHeld = false;
let toggleMode = false; // click-to-toggle fallback

const MIN_MS = 500;
document.addEventListener("pointerdown", unlockAudio, { once: true });
document.addEventListener("keydown", unlockAudio, { once: true });

const PTT_HINT = "Hold Space / button";

function appendBubble(el) {
  transcript.appendChild(el);
  transcript.scrollTop = transcript.scrollHeight;
}

function addBubble(role, text, status) {
  const el = document.createElement("div");
  el.className = `bubble ${role === "you" ? "you" : "argus"}`;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "you" ? "You" : "Argus";
  el.appendChild(who);
  const body = document.createElement("div");
  body.className = "body";
  body.textContent = text;
  el.appendChild(body);
  // Only surface actionable / error states — never "completed" or "voice".
  if (status === "error" || status === "awaiting_confirm") {
    const st = document.createElement("div");
    st.className = "status";
    st.textContent = status === "awaiting_confirm" ? "needs confirmation" : status;
    el.appendChild(st);
  }
  appendBubble(el);
}

function waveformBars(seedText) {
  // Deterministic pseudo-random bars from transcript so each clip looks distinct.
  let h = 0;
  for (let i = 0; i < seedText.length; i++) h = (h * 31 + seedText.charCodeAt(i)) >>> 0;
  const parts = [];
  for (let i = 0; i < 18; i++) {
    h = (h * 1103515245 + 12345) >>> 0;
    const tall = 4 + (h % 12);
    parts.push(`<span style="--h:${tall}px"></span>`);
  }
  return parts.join("");
}

function addVoiceBubble(transcriptText) {
  const el = document.createElement("div");
  el.className = "bubble you voice";

  const who = document.createElement("span");
  who.className = "who";
  who.textContent = "You";
  el.appendChild(who);

  const row = document.createElement("div");
  row.className = "voice-row";

  const wave = document.createElement("div");
  wave.className = "waveform";
  wave.setAttribute("aria-hidden", "true");
  wave.innerHTML = waveformBars(transcriptText || "voice");
  row.appendChild(wave);

  const chevron = document.createElement("button");
  chevron.type = "button";
  chevron.className = "voice-chevron";
  chevron.setAttribute("aria-expanded", "true");
  chevron.setAttribute("aria-label", "Hide transcript");
  chevron.textContent = "⌃";
  row.appendChild(chevron);
  el.appendChild(row);

  const details = document.createElement("div");
  details.className = "voice-transcript";
  details.textContent = transcriptText;
  el.appendChild(details);

  chevron.addEventListener("click", () => {
    const open = !details.classList.contains("collapsed");
    details.classList.toggle("collapsed", open);
    chevron.classList.toggle("collapsed", open);
    chevron.setAttribute("aria-expanded", open ? "false" : "true");
    chevron.setAttribute("aria-label", open ? "Show transcript" : "Hide transcript");
  });

  appendBubble(el);
}

function setBusy(v) {
  busy = v;
  sendBtn.disabled = v;
  btnYes.disabled = v;
  btnNo.disabled = v;
  input.disabled = v;
  if (voiceEnabled && !capturing) pttBtn.disabled = v;
}

function setRecordingUi(on) {
  pttBtn.classList.toggle("recording", on);
  pttBtn.textContent = on ? "Release to send" : PTT_HINT;
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

// Keep one Audio element + unlock on a real user gesture so playback
// still works after the async STT/LLM/TTS round-trip (autoplay policy).
let replyAudio = null;
let audioUnlocked = false;

function unlockAudio() {
  if (audioUnlocked) return;
  try {
    if (!replyAudio) replyAudio = new Audio();
    // Tiny silent wav — play() during gesture unlocks subsequent plays.
    replyAudio.src =
      "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=";
    const p = replyAudio.play();
    if (p && typeof p.then === "function") {
      p.then(() => {
        replyAudio.pause();
        replyAudio.currentTime = 0;
        audioUnlocked = true;
      }).catch(() => {});
    } else {
      audioUnlocked = true;
    }
  } catch (_) {}
}

function playAudioBase64(b64, mime) {
  if (!b64) return;
  try {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: mime || "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    if (!replyAudio) replyAudio = new Audio();
    if (replyAudio._objectUrl) URL.revokeObjectURL(replyAudio._objectUrl);
    replyAudio._objectUrl = url;
    replyAudio.src = url;
    replyAudio.onended = () => {
      if (replyAudio._objectUrl) {
        URL.revokeObjectURL(replyAudio._objectUrl);
        replyAudio._objectUrl = null;
      }
    };
    const p = replyAudio.play();
    if (p && typeof p.catch === "function") {
      p.catch((err) => {
        console.warn("TTS playback blocked:", err);
        addBubble("argus", "Reply audio blocked by the browser — click once in the page, then try voice again.", "error");
      });
    }
  } catch (err) {
    console.warn("TTS decode failed:", err);
  }
}

function handleTurn(data, { transcriptText } = {}) {
  if (transcriptText) addVoiceBubble(transcriptText);
  addBubble("argus", data.reply, data.status);
  if (data.audio_base64) {
    playAudioBase64(data.audio_base64, data.audio_mime);
  } else if (transcriptText && data.status === "completed" && data.reply) {
    const hint = (data.audio_mime && String(data.audio_mime).startsWith("error:"))
      ? data.audio_mime.slice(6)
      : "TTS skipped or failed";
    console.warn("Voice reply missing audio_base64", data.audio_mime);
    addBubble("argus", `No spoken reply: ${hint}`, "error");
  }
  if (data.status === "awaiting_confirm") showConfirm(data);
  else hideConfirm();
}

async function postVoice(blob) {
  const sid = await ensureSession();
  const body = new FormData();
  body.append("session_id", sid);
  body.append("audio", blob, "ptt.wav");
  const res = await fetch("/api/voice", { method: "POST", body });
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string" ? detail : (detail && detail.msg) || "Voice failed"
    );
  }
  sessionId = data.session_id;
  localStorage.setItem("argus_session_id", sessionId);
  return data;
}

function encodeWavFromChannel(channel, sampleRate) {
  const buffer = new ArrayBuffer(44 + channel.length * 2);
  const view = new DataView(buffer);
  const writeStr = (o, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + channel.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, channel.length * 2, true);
  let idx = 44;
  for (let i = 0; i < channel.length; i++, idx += 2) {
    const s = Math.max(-1, Math.min(1, channel[i]));
    view.setInt16(idx, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function downsample(channel, fromRate, toRate) {
  if (fromRate === toRate) return channel;
  const ratio = fromRate / toRate;
  const newLen = Math.max(1, Math.round(channel.length / ratio));
  const out = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    const idx = Math.min(channel.length - 1, Math.floor(i * ratio));
    out[i] = channel[idx];
  }
  return out;
}

async function recordedBlobToWav(blob) {
  const ctx = new AudioContext();
  try {
    await ctx.resume();
    const ab = await blob.arrayBuffer();
    const decoded = await ctx.decodeAudioData(ab.slice(0));
    let channel = decoded.getChannelData(0);
    // Mixdown if somehow stereo
    if (decoded.numberOfChannels > 1) {
      const mixed = new Float32Array(decoded.length);
      for (let c = 0; c < decoded.numberOfChannels; c++) {
        const data = decoded.getChannelData(c);
        for (let i = 0; i < data.length; i++) mixed[i] += data[i] / decoded.numberOfChannels;
      }
      channel = mixed;
    }
    const targetRate = 16000;
    const samples = downsample(channel, decoded.sampleRate, targetRate);
    // Reject near-silence
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      const a = Math.abs(samples[i]);
      if (a > peak) peak = a;
    }
    if (peak < 0.01) {
      throw new Error("Audio too quiet — check mic permissions / speak louder.");
    }
    return encodeWavFromChannel(samples, targetRate);
  } finally {
    await ctx.close().catch(() => {});
  }
}

function pickRecorderMime() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  for (const m of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

async function startRecording() {
  if (busy || !voiceEnabled || capturing) return;
  unlockAudio();
  recordChunks = [];
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (err) {
    throw new Error(
      "Microphone blocked. Allow mic access for this site, then try again."
    );
  }

  const mime = pickRecorderMime();
  mediaRecorder = mime
    ? new MediaRecorder(mediaStream, { mimeType: mime })
    : new MediaRecorder(mediaStream);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordChunks.push(e.data);
  };
  mediaRecorder.start(100); // timeslice so short holds still get chunks
  capturing = true;
  captureStartedAt = Date.now();
  setRecordingUi(true);
}

async function stopRecording() {
  if (!capturing || !mediaRecorder) return;
  const recorder = mediaRecorder;
  mediaRecorder = null;
  capturing = false;
  setRecordingUi(false);
  toggleMode = false;

  const elapsed = Date.now() - captureStartedAt;
  await new Promise((resolve) => {
    recorder.onstop = resolve;
    try {
      if (recorder.state !== "inactive") recorder.stop();
      else resolve();
    } catch (_) {
      resolve();
    }
  });

  (mediaStream?.getTracks() || []).forEach((t) => t.stop());
  mediaStream = null;

  if (elapsed < MIN_MS) {
    addBubble("argus", `Hold at least ${MIN_MS / 1000}s (Space or button).`, "error");
    recordChunks = [];
    return;
  }

  const rawBlob = new Blob(recordChunks, { type: recorder.mimeType || "audio/webm" });
  recordChunks = [];
  if (!rawBlob.size) {
    addBubble("argus", "No audio captured — try Space bar hold-to-talk.", "error");
    return;
  }

  setBusy(true);
  try {
    const wav = await recordedBlobToWav(rawBlob);
    const data = await postVoice(wav);
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

// Mouse/touch: press-and-hold on the button (no pointerleave cancel).
pttBtn.addEventListener("pointerdown", (e) => {
  if (e.button !== undefined && e.button !== 0) return;
  e.preventDefault();
  pttBtn.setPointerCapture?.(e.pointerId);
  startRecording().catch((err) => {
    addBubble("argus", String(err.message || err), "error");
  });
});
pttBtn.addEventListener("pointerup", () => {
  stopRecording().catch((err) => {
    addBubble("argus", String(err.message || err), "error");
  });
});
pttBtn.addEventListener("pointercancel", () => {
  if (capturing) stopRecording().catch(() => {});
});
// Double-click toggles recording for accessibility / trackpads.
pttBtn.addEventListener("dblclick", (e) => {
  e.preventDefault();
  if (!voiceEnabled || busy) return;
  if (!capturing) {
    toggleMode = true;
    startRecording().catch((err) => addBubble("argus", String(err.message || err), "error"));
  } else {
    stopRecording().catch((err) => addBubble("argus", String(err.message || err), "error"));
  }
});

function isTypingTarget(el) {
  if (!el) return false;
  const tag = (el.tagName || "").toLowerCase();
  return tag === "textarea" || tag === "input" || el.isContentEditable;
}

// Keyboard PTT: hold Space (when not typing) or Ctrl+Space anywhere.
window.addEventListener("keydown", (e) => {
  if (!voiceEnabled || busy) return;
  const space = e.code === "Space" || e.key === " ";
  if (!space) return;
  const typing = isTypingTarget(document.activeElement);
  if (typing && !e.ctrlKey) return; // allow spaces while composing text
  if (e.repeat || spaceHeld) return;
  e.preventDefault();
  spaceHeld = true;
  startRecording().catch((err) => {
    spaceHeld = false;
    addBubble("argus", String(err.message || err), "error");
  });
});

window.addEventListener("keyup", (e) => {
  const space = e.code === "Space" || e.key === " ";
  if (!space || !spaceHeld) return;
  spaceHeld = false;
  e.preventDefault();
  stopRecording().catch((err) => {
    addBubble("argus", String(err.message || err), "error");
  });
});

window.addEventListener("blur", () => {
  if (spaceHeld || capturing) {
    spaceHeld = false;
    stopRecording().catch(() => {});
  }
});

(async () => {
  try {
    const health = await fetch("/api/health").then((r) => r.json());
    await ensureSession();
    voiceEnabled = !!health.voice_enabled;
    pttBtn.disabled = !voiceEnabled;
    pttBtn.textContent = voiceEnabled ? PTT_HINT : "Voice off";
    meta.textContent = voiceEnabled
      ? `${health.model} · voice on · Space=PTT`
      : `${health.model} · text only`;
  } catch {
    meta.textContent = "offline";
  }
  input.focus();
})();
