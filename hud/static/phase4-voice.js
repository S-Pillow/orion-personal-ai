"use strict";

const MAX_RECORDING_MS = 20000;
const MAX_TTS_TEXT_CHARS = 4000;
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
];
const CHAT_STREAM_PATH_RE = /^\/api\/orion\/sessions\/[^/]+\/chat\/stream$/;

const composer = document.getElementById("composer");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const stopButton = document.getElementById("stopButton");
const sessionSelect = document.getElementById("sessionSelect");
const transcript = document.getElementById("transcript");
const composerActions = sendButton?.closest(".composer-actions");

if (
  composer &&
  messageInput &&
  sendButton &&
  stopButton &&
  sessionSelect &&
  transcript &&
  composerActions
) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/phase4-voice.css";
  document.head.append(stylesheet);

  composerActions.classList.add("phase4-voice-actions");

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

  composerActions.insertBefore(voiceButton, sendButton);
  composerActions.insertBefore(speakButton, sendButton);

  const status = document.createElement("div");
  status.id = "phase4VoiceStatus";
  status.className = "phase4-voice-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.textContent = "VOICE · PUSH TO TALK · WAKE OFF";
  composer.insertAdjacentElement("afterend", status);

  let mediaStream = null;
  let recorder = null;
  let recordingSessionId = null;
  let microphonePending = false;
  let transcriptionPending = false;
  let pendingVoiceSubmission = null;
  let submittingPendingVoice = false;
  let pendingRunInterruption = false;
  let chunks = [];
  let stopTimer = null;
  let speakReplies = true;
  let activeAudio = null;
  let activeAudioResolve = null;
  let activeSpeechController = null;
  let speechEpoch = 0;
  let speechQueue = Promise.resolve();
  let voiceTurn = null;

  function setStatus(text, detail = "") {
    status.textContent = detail ? `VOICE · ${text} · ${detail}` : `VOICE · ${text}`;
    status.dataset.voiceState = text.toLowerCase().replaceAll(" ", "_");
  }

  function parseVoiceSseFrame(frame) {
    let eventName = "";
    const dataLines = [];
    for (const line of String(frame || "").split(/\r?\n/)) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return null;
    try {
      const data = JSON.parse(dataLines.join("\n"));
      return { event: eventName || data?.event || "message", data };
    } catch {
      return null;
    }
  }

  function observeAssistantStreamFrame(frame) {
    if (!voiceTurn) return;
    const parsed = parseVoiceSseFrame(frame);
    if (!parsed) return;

    if (parsed.event === "assistant.delta") {
      const delta = String(parsed.data?.delta || "");
      if (!delta) return;
      voiceTurn.sourceText += delta;
      queueCompletedSpeech();
      return;
    }

    if (parsed.event === "assistant.completed") {
      const content = typeof parsed.data?.content === "string"
        ? parsed.data.content
        : "";
      // Most Hermes streams provide all source text through assistant.delta.
      // Use completed content only when no deltas were observed, or when it is
      // a strict append-compatible completion of the captured source.
      if (!voiceTurn.sourceText && content) voiceTurn.sourceText = content;
      else if (content.startsWith(voiceTurn.sourceText)) voiceTurn.sourceText = content;
      queueCompletedSpeech();
    }
  }

  function requestTargetsChatStream(input, options = {}) {
    const request = input instanceof Request ? input : null;
    const method = String(options.method || request?.method || "GET").toUpperCase();
    if (method !== "POST") return false;
    try {
      const rawUrl = request?.url || String(input || "");
      const url = new URL(rawUrl, window.location.href);
      return url.origin === window.location.origin && CHAT_STREAM_PATH_RE.test(url.pathname);
    } catch {
      return false;
    }
  }

  function wrapChatStreamResponse(response) {
    if (!response.body || typeof TransformStream !== "function") return response;

    const decoder = new TextDecoder();
    let buffer = "";

    function consumeFrames(final = false) {
      let splitAt;
      while ((splitAt = buffer.search(/\r?\n\r?\n/)) >= 0) {
        const match = buffer.match(/\r?\n\r?\n/);
        const delimiterLength = match ? match[0].length : 2;
        const frame = buffer.slice(0, splitAt);
        buffer = buffer.slice(splitAt + delimiterLength);
        observeAssistantStreamFrame(frame);
      }
      if (final && buffer.trim()) {
        observeAssistantStreamFrame(buffer);
        buffer = "";
      }
    }

    const observer = new TransformStream({
      transform(chunk, controller) {
        buffer += decoder.decode(chunk, { stream: true });
        consumeFrames(false);
        controller.enqueue(chunk);
      },
      flush() {
        buffer += decoder.decode();
        consumeFrames(true);
      },
    });

    return new Response(response.body.pipeThrough(observer), {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }

  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const response = await nativeFetch(input, options);
    if (!requestTargetsChatStream(input, options)) return response;
    return wrapChatStreamResponse(response);
  };

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

  function sessionStillSelected(sessionId) {
    return Boolean(sessionId && sessionSelect.value === sessionId);
  }

  function recorderIsActive() {
    return Boolean(recorder && recorder.state !== "inactive");
  }

  function syncVoiceButtonAvailability() {
    voiceButton.disabled = !recorderIsActive() && (
      microphonePending ||
      transcriptionPending ||
      Boolean(pendingVoiceSubmission)
    );
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
    recordingSessionId = null;
    microphonePending = false;
    chunks = [];
    voiceButton.textContent = "PUSH TO TALK";
    voiceButton.setAttribute("aria-pressed", "false");
    syncVoiceButtonAvailability();
  }

  function stopSpeechPlayback() {
    speechEpoch += 1;
    if (activeSpeechController) {
      activeSpeechController.abort();
      activeSpeechController = null;
    }
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

  function tryIssuePendingRunInterruption() {
    if (!pendingRunInterruption || stopButton.disabled) return false;
    pendingRunInterruption = false;
    stopButton.click();
    return true;
  }

  function interruptSpeechAndRun() {
    voiceTurn = null;
    stopSpeechPlayback();
    const priorRunBusy = sendButton.disabled || !stopButton.disabled;
    pendingRunInterruption = priorRunBusy;
    tryIssuePendingRunInterruption();
  }

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("audio_read_failed"));
      reader.readAsDataURL(blob);
    });
  }

  function discardPendingSubmission(detail) {
    pendingVoiceSubmission = null;
    submittingPendingVoice = false;
    syncVoiceButtonAvailability();
    setStatus("PUSH TO TALK", detail);
  }

  function trySubmitPendingVoice() {
    if (!pendingVoiceSubmission || submittingPendingVoice) return false;
    const pending = pendingVoiceSubmission;

    if (!sessionStillSelected(pending.sessionId)) {
      discardPendingSubmission("SESSION CHANGED · TRANSCRIPT NOT SENT · WAKE OFF");
      return false;
    }

    if (sendButton.disabled || sessionSelect.disabled) {
      setStatus("CONVERSATION", "WAITING FOR PRIOR RUN TO STOP · WAKE OFF");
      return false;
    }

    submittingPendingVoice = true;
    messageInput.value = pending.text;
    messageInput.dispatchEvent(new Event("input", { bubbles: true }));
    composer.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    // app.js synchronously disables Send before awaiting the stream fetch when
    // a turn is accepted. If it remains enabled, keep the transcript pending
    // rather than claiming that the message was sent.
    if (!sendButton.disabled) {
      submittingPendingVoice = false;
      setStatus("CONVERSATION", "TRANSCRIPT READY · WAITING TO SUBMIT · WAKE OFF");
      return false;
    }

    pendingVoiceSubmission = null;
    submittingPendingVoice = false;
    voiceTurn = speakReplies
      ? {
          sourceText: "",
          queuedChars: 0,
          finalFlushed: false,
        }
      : null;
    syncVoiceButtonAvailability();
    setStatus("CONVERSATION", "TRANSCRIPT SENT · WAKE OFF");
    return true;
  }

  function queueTranscriptSubmission(text, sessionId) {
    if (!sessionStillSelected(sessionId)) {
      setStatus("PUSH TO TALK", "SESSION CHANGED · TRANSCRIPT NOT SENT · WAKE OFF");
      return;
    }
    const clean = String(text || "").trim();
    if (!clean) {
      setStatus("PUSH TO TALK", "NO SPEECH DETECTED · WAKE OFF");
      return;
    }
    pendingVoiceSubmission = { text: clean, sessionId };
    syncVoiceButtonAvailability();
    trySubmitPendingVoice();
  }

  async function transcribe(blob, sessionId) {
    if (!sessionStillSelected(sessionId)) {
      setStatus("PUSH TO TALK", "SESSION CHANGED · RECORDING DISCARDED · WAKE OFF");
      return;
    }
    setStatus("CONVERSATION", "TRANSCRIBING · WAKE OFF");
    const dataUrl = await blobToDataUrl(blob);
    if (!sessionStillSelected(sessionId)) {
      setStatus("PUSH TO TALK", "SESSION CHANGED · RECORDING DISCARDED · WAKE OFF");
      return;
    }
    const payload = await jsonApi("/api/orion/voice/transcribe", {
      method: "POST",
      body: JSON.stringify({ data_url: dataUrl, mime_type: blob.type || "audio/webm" }),
    });
    queueTranscriptSubmission(payload.transcript || "", sessionId);
  }

  async function startRecording() {
    if (microphonePending || transcriptionPending || pendingVoiceSubmission) return;

    const sessionId = sessionSelect.value;
    if (!sessionId) {
      setStatus("PUSH TO TALK", "SELECT OR CREATE A SESSION");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("OFF", "BROWSER MICROPHONE CAPTURE UNAVAILABLE");
      return;
    }

    interruptSpeechAndRun();
    recordingSessionId = sessionId;
    microphonePending = true;
    syncVoiceButtonAvailability();
    setStatus("CONVERSATION", "REQUESTING MICROPHONE · WAKE OFF");
    const mimeType = supportedMimeType();

    try {
      const acquiredStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!sessionStillSelected(sessionId)) {
        for (const track of acquiredStream.getTracks()) track.stop();
        releaseMicrophone();
        setStatus("PUSH TO TALK", "SESSION CHANGED · RECORDING CANCELLED · WAKE OFF");
        return;
      }

      mediaStream = acquiredStream;
      recorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);
      chunks = [];
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data?.size) chunks.push(event.data);
      });
      recorder.addEventListener("stop", async () => {
        const boundSessionId = recordingSessionId;
        const type = recorder?.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        releaseMicrophone();
        if (!sessionStillSelected(boundSessionId)) {
          setStatus("PUSH TO TALK", "SESSION CHANGED · RECORDING DISCARDED · WAKE OFF");
          return;
        }
        if (!blob.size) {
          setStatus("PUSH TO TALK", "EMPTY RECORDING · WAKE OFF");
          return;
        }

        transcriptionPending = true;
        syncVoiceButtonAvailability();
        try {
          await transcribe(blob, boundSessionId);
        } catch (error) {
          setStatus("PUSH TO TALK", `TRANSCRIPTION FAILED · ${error.message}`);
        } finally {
          transcriptionPending = false;
          syncVoiceButtonAvailability();
        }
      }, { once: true });
      recorder.start();
      microphonePending = false;
      syncVoiceButtonAvailability();
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
    if (!recorderIsActive()) return;
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
    const controller = new AbortController();
    activeSpeechController = controller;
    try {
      const payload = await jsonApi("/api/orion/voice/speak", {
        method: "POST",
        body: JSON.stringify({ text: clean }),
        signal: controller.signal,
      });
      if (!speakReplies || controller.signal.aborted) return;
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
    } finally {
      if (activeSpeechController === controller) activeSpeechController = null;
    }
  }

  function speechText(text) {
    return String(text || "")
      .replace(/^#{2,3}\s+/gm, "")
      .replace(/^[-*]\s+/gm, "")
      .replace(/^\d+\.\s+/gm, "")
      .replace(/\*\*([^*\n]+)\*\*/g, "$1")
      .replace(/`([^`\n]+)`/g, "$1")
      .trim();
  }

  function splitSpeechForTts(text) {
    let remaining = speechText(text);
    const parts = [];
    while (remaining.length > MAX_TTS_TEXT_CHARS) {
      let cut = remaining.lastIndexOf(" ", MAX_TTS_TEXT_CHARS);
      if (cut <= 0) cut = MAX_TTS_TEXT_CHARS;
      const part = remaining.slice(0, cut).trim();
      if (part) parts.push(part);
      remaining = remaining.slice(cut).trimStart();
    }
    if (remaining) parts.push(remaining);
    return parts;
  }

  function enqueueSpeech(text) {
    const parts = splitSpeechForTts(text);
    if (!parts.length || !speakReplies) return;
    const epoch = speechEpoch;
    for (const clean of parts) {
      speechQueue = speechQueue
        .then(() => {
          if (!speakReplies || epoch !== speechEpoch) return undefined;
          return playSpeech(clean);
        })
        .catch((error) => {
          if (epoch !== speechEpoch || error?.name === "AbortError") return;
          setStatus("PUSH TO TALK", `TTS FAILED · ${error.message}`);
        });
    }
  }

  function extractCompletedSpeechPrefix(text) {
    let remaining = String(text || "");
    let consumed = 0;
    const speechChunks = [];

    while (remaining) {
      const match = remaining.match(/^([\s\S]*?(?:[.!?](?=\s)|\n+))(\s*)/);
      if (!match) break;
      const advance = match[0].length;
      if (!advance) break;
      const chunk = match[1].trim();
      if (chunk) speechChunks.push(chunk);
      consumed += advance;
      remaining = remaining.slice(advance);
    }

    return { chunks: speechChunks, consumed };
  }

  function queueCompletedSpeech() {
    if (!voiceTurn || !speakReplies) return;
    const remainder = voiceTurn.sourceText.slice(voiceTurn.queuedChars);
    if (!remainder) return;
    const completed = extractCompletedSpeechPrefix(remainder);
    for (const chunk of completed.chunks) enqueueSpeech(chunk);
    if (completed.consumed) voiceTurn.queuedChars += completed.consumed;
  }

  function flushFinalSpeech() {
    if (!voiceTurn || voiceTurn.finalFlushed) return;
    const remainder = voiceTurn.sourceText.slice(voiceTurn.queuedChars).trim();
    if (remainder) enqueueSpeech(remainder);
    voiceTurn.finalFlushed = true;
    voiceTurn = null;
    setStatus("PUSH TO TALK", "WAKE OFF");
  }

  const stopObserver = new MutationObserver(() => {
    tryIssuePendingRunInterruption();
  });
  stopObserver.observe(stopButton, { attributes: true, attributeFilter: ["disabled"] });

  const sendObserver = new MutationObserver(() => {
    if (pendingRunInterruption && !sendButton.disabled && stopButton.disabled) {
      pendingRunInterruption = false;
    }
    if (pendingVoiceSubmission && !sendButton.disabled) {
      trySubmitPendingVoice();
    }
    if (!sendButton.disabled && voiceTurn) flushFinalSpeech();
  });
  sendObserver.observe(sendButton, { attributes: true, attributeFilter: ["disabled"] });

  voiceButton.addEventListener("click", () => {
    if (recorderIsActive()) stopRecording();
    else startRecording();
  });

  speakButton.addEventListener("click", () => {
    speakReplies = !speakReplies;
    speakButton.setAttribute("aria-pressed", String(speakReplies));
    speakButton.textContent = `SPEAK REPLIES: ${speakReplies ? "ON" : "OFF"}`;
    if (!speakReplies) {
      voiceTurn = null;
      stopSpeechPlayback();
    }
  });

  sessionSelect.addEventListener("change", () => {
    if (pendingVoiceSubmission && !sessionStillSelected(pendingVoiceSubmission.sessionId)) {
      discardPendingSubmission("SESSION CHANGED · TRANSCRIPT NOT SENT · WAKE OFF");
    }
  });

  window.addEventListener("beforeunload", () => {
    if (recorderIsActive()) recorder.stop();
    releaseMicrophone();
    pendingVoiceSubmission = null;
    pendingRunInterruption = false;
    voiceTurn = null;
    stopSpeechPlayback();
    window.fetch = nativeFetch;
  });

  jsonApi("/api/orion/voice/status")
    .then((payload) => {
      if (payload?.voice?.ready) setStatus("PUSH TO TALK", "WAKE OFF");
      else setStatus("OFF", payload?.voice?.reason || "HERMES VOICE UNAVAILABLE");
    })
    .catch((error) => setStatus("OFF", error.message));
}
