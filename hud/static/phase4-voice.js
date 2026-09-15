"use strict";

const MAX_RECORDING_MS = 20000;
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

const composer = document.getElementById("composer");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");
const sessionSelect = document.getElementById("sessionSelect");
const transcript = document.getElementById("transcript");

if (composer && messageInput && sendButton && stopButton && sessionSelect && transcript) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/phase4-voice.css";
  document.head.append(stylesheet);

  const voiceButton = document.createElement("button");
  voiceButton.id = "voiceButton";
  voiceButton.className = "outline-button phase4-voice-button";
  voiceButton.type = "button";
  voiceButton.textContent = "PUSH TO TALK";
  voiceButton.setAttribute("aria-pressed", "false");

  const speakButton = document.createElement("button");
  speakButton.id = "voiceReplyToggle";
  speakButton.className = "outline-button phase4-voice-toggle";
  speakButton.type = "button";
  speakButton.textContent = "SPEAK REPLIES: ON";
  speakButton.setAttribute("aria-pressed", "true");

  composer.insertBefore(voiceButton, sendButton);
  composer.insertBefore(speakButton, sendButton);

  const status = document.createElement("div");
  status.id = "phase4VoiceStatus";
  status.className = "phase4-voice-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.textContent = "VOICE · PUSH TO TALK · WAKE OFF";
  composer.insertAdjacentElement("afterend", status);

  let mediaStream = null;
  let recorder = null;
  let chunks = [];
  let stopTimer = null;
  let speakReplies = true;
  let activeAudio = null;
  let activeAudioResolve = null;
  let speechEpoch = 0;
  let speechQueue = Promise.resolve();
  let voiceTurn = null;

  function setStatus(text, detail = "") {
    status.textContent = detail ? `VOICE · ${text} · ${detail}` : `VOICE · ${text}`;
    status.dataset.voiceState = text.toLowerCase().replaceAll(" ", "_");
  }

  async function jsonApi(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  function supportedMimeType() {
    if (!window.MediaRecorder) return "";
    return MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";
  }

  function releaseMicrophone() {
    if (stopTimer) {
      clearTimeout(stopTimer);
      stopTimer = null;
    }
    if (mediaStream) {
      for (const track of mediaStream.getTracks()) track.stop();
      mediaStream = null;
    }
    recorder = null;
    chunks = [];
    voiceButton.textContent = "PUSH TO TALK";
    voiceButton.setAttribute("aria-pressed", "false");
  }

  function stopSpeechPlayback() {
    speechEpoch += 1;
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.src = "";
      activeAudio = null;
    }
    if (activeAudioResolve) {
      activeAudioResolve();
      activeAudioResolve = null;
    }
    speechQueue = Promise.resolve();
  }

  function interruptSpeechAndRun() {
    stopSpeechPlayback();
    if (!stopButton.disabled) stopButton.click();
  }

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("audio_read_failed"));
      reader.readAsDataURL(blob);
    });
  }

  function submitTranscript(text) {
    const clean = String(text || "").trim();
    if (!clean) {
      setStatus("PUSH TO TALK", "NO SPEECH DETECTED · WAKE OFF");
      return;
    }
    messageInput.value = clean;
    messageInput.dispatchEvent(new Event("input", { bubbles: true }));
    voiceTurn = { body: null, queuedChars: 0, finalFlushed: false };
    composer.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    setStatus("CONVERSATION", "TRANSCRIPT SENT · WAKE OFF");
  }

  async function transcribe(blob) {
    setStatus("CONVERSATION", "TRANSCRIBING · WAKE OFF");
    const dataUrl = await blobToDataUrl(blob);
    const payload = await jsonApi("/api/orion/voice/transcribe", {
      method: "POST",
      body: JSON.stringify({ data_url: dataUrl, mime_type: blob.type || "audio/webm" }),
    });
    submitTranscript(payload.transcript || "");
  }

  async function startRecording() {
    if (!sessionSelect.value) {
      setStatus("PUSH TO TALK", "SELECT OR CREATE A SESSION");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("OFF", "BROWSER MICROPHONE CAPTURE UNAVAILABLE");
      return;
    }

    interruptSpeechAndRun();
    const mimeType = supportedMimeType();
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);
      chunks = [];
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data?.size) chunks.push(event.data);
      });
      recorder.addEventListener("stop", async () => {
        const type = recorder?.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        releaseMicrophone();
        if (!blob.size) {
          setStatus("PUSH TO TALK", "EMPTY RECORDING · WAKE OFF");
          return;
        }
        try {
          await transcribe(blob);
        } catch (error) {
          setStatus("PUSH TO TALK", `TRANSCRIPTION FAILED · ${error.message}`);
        }
      }, { once: true });
      recorder.start();
      voiceButton.textContent = "STOP LISTENING";
      voiceButton.setAttribute("aria-pressed", "true");
      setStatus("CONVERSATION", "LISTENING · WAKE OFF");
      stopTimer = window.setTimeout(() => stopRecording("20S SAFETY LIMIT"), MAX_RECORDING_MS);
    } catch (error) {
      releaseMicrophone();
      setStatus("PUSH TO TALK", `MICROPHONE UNAVAILABLE · ${error.name || "ERROR"}`);
    }
  }

  function stopRecording(reason = "TRANSCRIBING") {
    if (!recorder || recorder.state === "inactive") return;
    if (stopTimer) {
      clearTimeout(stopTimer);
      stopTimer = null;
    }
    setStatus("CONVERSATION", `${reason} · WAKE OFF`);
    recorder.stop();
  }

  async function playSpeech(text) {
    const clean = String(text || "").trim();
    if (!speakReplies || !clean) return;
    const payload = await jsonApi("/api/orion/voice/speak", {
      method: "POST",
      body: JSON.stringify({ text: clean }),
    });
    if (!payload.data_url) throw new Error("Hermes TTS returned no audio");
    await new Promise((resolve, reject) => {
      const audio = new Audio(payload.data_url);
      activeAudio = audio;
      activeAudioResolve = resolve;
      audio.addEventListener("ended", () => {
        if (activeAudio === audio) activeAudio = null;
        if (activeAudioResolve === resolve) activeAudioResolve = null;
        resolve();
      }, { once: true });
      audio.addEventListener("error", () => {
        if (activeAudio === audio) activeAudio = null;
        if (activeAudioResolve === resolve) activeAudioResolve = null;
        reject(new Error("audio_playback_failed"));
      }, { once: true });
      audio.play().catch(reject);
    });
  }

  function enqueueSpeech(text) {
    const clean = String(text || "").trim();
    if (!clean || !speakReplies) return;
    const epoch = speechEpoch;
    speechQueue = speechQueue
      .then(() => {
        if (!speakReplies || epoch !== speechEpoch) return undefined;
        return playSpeech(clean);
      })
      .catch((error) => setStatus("PUSH TO TALK", `TTS FAILED · ${error.message}`));
  }

  function latestAssistantBody() {
    const nodes = transcript.querySelectorAll(".message.assistant .message-body");
    return nodes.length ? nodes[nodes.length - 1] : null;
  }

  function queueCompletedSpeech() {
    if (!voiceTurn || !speakReplies) return;
    const body = latestAssistantBody();
    if (!body) return;
    if (voiceTurn.body !== body) {
      voiceTurn.body = body;
      voiceTurn.queuedChars = 0;
      voiceTurn.finalFlushed = false;
    }
    const text = String(body.textContent || "");
    const remainder = text.slice(voiceTurn.queuedChars);
    if (!remainder) return;

    let consumed = 0;
    const sentencePattern = /[^.!?\n]+[.!?](?:\s+|$)|[^\n]+\n+/g;
    for (const match of remainder.matchAll(sentencePattern)) {
      const chunk = match[0].trim();
      consumed = (match.index || 0) + match[0].length;
      if (chunk) enqueueSpeech(chunk);
    }
    if (consumed) voiceTurn.queuedChars += consumed;
  }

  function flushFinalSpeech() {
    if (!voiceTurn || voiceTurn.finalFlushed) return;
    const body = voiceTurn.body || latestAssistantBody();
    if (!body) return;
    const text = String(body.textContent || "");
    const remainder = text.slice(voiceTurn.queuedChars).trim();
    if (remainder) enqueueSpeech(remainder);
    voiceTurn.finalFlushed = true;
    voiceTurn = null;
    setStatus("PUSH TO TALK", "WAKE OFF");
  }

  const transcriptObserver = new MutationObserver(() => queueCompletedSpeech());
  transcriptObserver.observe(transcript, { childList: true, subtree: true, characterData: true });

  const sendObserver = new MutationObserver(() => {
    if (!sendButton.disabled && voiceTurn) flushFinalSpeech();
  });
  sendObserver.observe(sendButton, { attributes: true, attributeFilter: ["disabled"] });

  voiceButton.addEventListener("click", () => {
    if (recorder && recorder.state !== "inactive") stopRecording();
    else startRecording();
  });

  speakButton.addEventListener("click", () => {
    speakReplies = !speakReplies;
    speakButton.setAttribute("aria-pressed", String(speakReplies));
    speakButton.textContent = `SPEAK REPLIES: ${speakReplies ? "ON" : "OFF"}`;
    if (!speakReplies) stopSpeechPlayback();
  });

  window.addEventListener("beforeunload", () => {
    if (recorder && recorder.state !== "inactive") recorder.stop();
    releaseMicrophone();
    stopSpeechPlayback();
  });

  jsonApi("/api/orion/voice/status")
    .then((payload) => {
      if (payload?.voice?.ready) setStatus("PUSH TO TALK", "WAKE OFF");
      else setStatus("OFF", payload?.voice?.reason || "HERMES VOICE UNAVAILABLE");
    })
    .catch((error) => setStatus("OFF", error.message));
}
