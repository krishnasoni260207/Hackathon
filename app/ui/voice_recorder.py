"""Browser-based voice recorder using Streamlit custom component.

Records audio from the user's microphone with speech detection and
automatic silence-based stopping. When the user speaks and then goes
silent for ~1.2 seconds, the recording auto-stops and sends the audio
back to Streamlit for processing.
"""
from __future__ import annotations

import base64
import binascii
from typing import Any

import streamlit as st


_VOICE_RECORDER = st.components.v2.component(
    "persistent_voice_recorder",
    html="<div></div>",
    js="""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;

  // ---------- per-element persistent state ----------
  const instances =
    component.__voiceRecorderInstances ||
    (component.__voiceRecorderInstances = new WeakMap());
  let state = instances.get(parentElement);

  if (!state) {
    state = {
      sessionId: null,
      stream: null,
      audioCtx: null,
      analyser: null,
      source: null,
      recorder: null,
      chunks: [],
      rafId: null,
      speechDetected: false,
      silentFrames: 0,
      audioPlayer: null,
      activeAudioRequestId: null,
      isAudioPlaying: false,
    };
    instances.set(parentElement, state);
  }

  // ---------- configuration ----------
  const SILENCE_MS   = Number(data?.silence_ms       || 1200);
  const THRESHOLD    = Number(data?.speech_threshold  || 0.02);
  // How often requestAnimationFrame fires (~16 ms at 60 fps).
  const FRAME_MS     = 16;
  const SILENCE_FRAMES = Math.ceil(SILENCE_MS / FRAME_MS);

  // ---------- helpers ----------
  const toBase64 = (arrayBuffer) => {
    let binary = "";
    const bytes = new Uint8Array(arrayBuffer);
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  };

  const stopAudioPlayback = () => {
    if (state.audioPlayer) {
      try {
        state.audioPlayer.pause();
        state.audioPlayer.currentTime = 0;
      } catch (_) {}
      state.isAudioPlaying = false;
    }
  };

  const cleanup = () => {
    if (state.rafId !== null) cancelAnimationFrame(state.rafId);
    state.rafId = null;
    stopAudioPlayback();
    if (state.recorder && state.recorder.state !== "inactive") {
      try { state.recorder.stop(); } catch (_) {}
    }
    state.recorder = null;
    state.chunks = [];
    state.speechDetected = false;
    state.silentFrames = 0;
    if (state.source)   state.source.disconnect();
    if (state.audioCtx) state.audioCtx.close();
    if (state.stream)   state.stream.getTracks().forEach(t => t.stop());
    state.source   = null;
    state.analyser = null;
    state.audioCtx = null;
    state.stream   = null;
    state.sessionId = null;
    state.activeAudioRequestId = null;
  };

  const emitAudio = (blob, sessionId) => {
    if (!blob || blob.size === 0) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      if (state.sessionId !== sessionId) return;
      setTriggerValue("speech", {
        session_id: sessionId,
        filename: "recording.webm",
        audio_base64: toBase64(reader.result),
        interrupted_request_id: state.interruptedRequestId || null,
      });
      state.interruptedRequestId = null;
    };
    reader.readAsArrayBuffer(blob);
  };

  const stopRecording = (sessionId) => {
    if (!state.recorder || state.recorder.state === "inactive") return;
    state.recorder.stop();
  };

  const startRecording = (sessionId) => {
    if (state.recorder) return;
    state.chunks = [];
    state.recorder = new MediaRecorder(state.stream, { mimeType: "audio/webm" });
    state.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) state.chunks.push(e.data);
    };
    state.recorder.onstop = () => {
      const blob = new Blob(state.chunks, { type: "audio/webm" });
      state.chunks = [];
      state.speechDetected = false;
      state.silentFrames = 0;
      emitAudio(blob, sessionId);
    };
    state.recorder.start();
  };

  // ---------- audio level monitor & interruption detection ----------
  const monitor = (sessionId) => {
    if (!state.analyser || state.sessionId !== sessionId) return;

    const samples = new Uint8Array(state.analyser.fftSize);
    state.analyser.getByteTimeDomainData(samples);

    // Compute RMS level
    let sum = 0;
    for (const s of samples) {
      const n = (s - 128) / 128;
      sum += n * n;
    }
    const level = Math.sqrt(sum / samples.length);

    if (level >= THRESHOLD) {
      // If assistant audio is playing and user speaks -> REAL VOICE INTERRUPTION!
      if (state.isAudioPlaying && state.audioPlayer && !state.audioPlayer.paused) {
        const interruptedReqId = state.activeAudioRequestId;
        stopAudioPlayback();
        state.interruptedRequestId = interruptedReqId;
        setTriggerValue("interrupted", {
          session_id: sessionId,
          request_id: interruptedReqId,
          timestamp: Date.now(),
        });
      }

      // Speech detected
      if (!state.speechDetected) {
        state.speechDetected = true;
        startRecording(sessionId);
      }
      state.silentFrames = 0;
    } else if (state.speechDetected) {
      // Silence after speech — count frames
      state.silentFrames++;
      if (state.silentFrames >= SILENCE_FRAMES) {
        // Enough silence — stop recording and submit
        stopRecording(sessionId);
        return;  // stop monitoring until next turn
      }
    }

    state.rafId = requestAnimationFrame(() => monitor(sessionId));
  };

  // ---------- Playback Control ----------
  if (data?.cancel_playback) {
    stopAudioPlayback();
  } else if (data?.play_audio_base64 && data?.play_request_id) {
    if (state.activeAudioRequestId !== String(data.play_request_id)) {
      state.activeAudioRequestId = String(data.play_request_id);
      if (!state.audioPlayer) {
        state.audioPlayer = new Audio();
      }
      state.audioPlayer.src = "data:audio/wav;base64," + data.play_audio_base64;
      state.isAudioPlaying = true;
      state.audioPlayer.onended = () => {
        state.isAudioPlaying = false;
        setTriggerValue("playback_ended", {
          session_id: sessionId,
          request_id: state.activeAudioRequestId,
        });
      };
      state.audioPlayer.play().catch(err => {
        console.warn("Audio autoplay blocked by browser policy:", err);
      });
    }
  }

  // ---------- start / stop based on Streamlit props ----------
  const start = async (sessionId) => {
    if (state.sessionId === sessionId) return;
    cleanup();
    state.sessionId = sessionId;

    try {
      // Request mic with echo cancellation so AI output doesn't falsely trigger speech
      state.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (state.sessionId !== sessionId) { cleanup(); return; }

      state.audioCtx  = new AudioContext();
      state.analyser  = state.audioCtx.createAnalyser();
      state.analyser.fftSize = 1024;
      state.source    = state.audioCtx.createMediaStreamSource(state.stream);
      state.source.connect(state.analyser);

      // Start monitoring — listens for speech and interruptions
      monitor(sessionId);
    } catch (err) {
      setTriggerValue("error", { session_id: sessionId, message: String(err) });
      cleanup();
    }
  };

  // React to stop_requested from Streamlit (manual submit button)
  if (data?.stop_requested && state.sessionId === String(data.session_id)) {
    if (state.recorder && state.recorder.state === "recording") {
      stopRecording(state.sessionId);
    }
  }

  // Main activation logic
  if (!data?.active) {
    if (state.sessionId !== null) cleanup();
    return () => cleanup();
  }

  start(String(data.session_id));
  return () => {};
}
""",
)


def render_voice_recorder(
    active: bool,
    session_id: str,
    play_audio_base64: str = "",
    play_request_id: str = "",
    cancel_playback: bool = False,
) -> dict[str, Any] | None:
    """Render the browser voice recorder and return captured audio or events.

    Handles continuous monitoring, instant speech-triggered interruption of audio,
    and voice submission upon silence.
    """
    result = _VOICE_RECORDER(
        key="persistent_voice_recorder",
        data={
            "active": active,
            "session_id": session_id,
            "stop_requested": st.session_state.get("recording_stop_requested", False),
            "speech_threshold": 0.02,
            "silence_ms": 1200,
            "play_audio_base64": play_audio_base64,
            "play_request_id": play_request_id,
            "cancel_playback": cancel_playback,
        },
        on_speech_change=lambda: None,
        on_interrupted_change=lambda: None,
        on_playback_ended_change=lambda: None,
        on_error_change=lambda: None,
        width="stretch",
        height=1,
    )

    if not result:
        return None

    # 1. Check for real-time interruption event
    interrupted = getattr(result, "interrupted", None)
    if interrupted:
        return {
            "type": "interrupted",
            "request_id": interrupted.get("request_id"),
            "timestamp": interrupted.get("timestamp"),
        }

    # 2. Check for speech recording submission
    speech = getattr(result, "speech", None)
    if speech:
        try:
            audio_bytes = base64.b64decode(speech["audio_base64"], validate=True)
            if audio_bytes:
                return {
                    "type": "speech",
                    "audio_data": audio_bytes,
                    "filename": speech.get("filename", "recording.webm"),
                    "interrupted_request_id": speech.get("interrupted_request_id"),
                }
        except (KeyError, TypeError, binascii.Error):
            pass

    # 3. Check for playback ended event
    playback_ended = getattr(result, "playback_ended", None)
    if playback_ended:
        return {
            "type": "playback_ended",
            "request_id": playback_ended.get("request_id"),
        }

    return None