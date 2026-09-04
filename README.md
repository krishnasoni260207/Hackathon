# Interruptible Study Assistant

A voice-first study assistant for university students.

The target user is a university student who wants to ask study questions out loud and receive spoken explanations. The main product problem is making an AI assistant feel natural during study sessions, especially when the student changes direction while the assistant is speaking.

The eventual goal is an interruptible assistant: when the AI is speaking, the student can interrupt naturally, the old response is stopped or marked invalid, and the new request is handled instead.

## Phase 1 Status

Phase 1 sets up the project structure, dependencies, environment placeholders, documentation, tests, and a runnable Streamlit UI.

Implemented:

- Project folders and Python packages.
- Streamlit UI with example study conversation.
- Placeholder status and voice controls.
- Future service status area for Speech-to-Text, LLM, Rime TTS, and LiveKit.
- Basic tests for current placeholder state.

Not implemented:

- Microphone streaming.
- Realtime STT.
- LLM calls.
- Rime TTS calls.
- Audio playback.
- LiveKit connection.
- Interruption detection.
- Cancellation, stale-response prevention, recovery, and latency measurements.

## Install

From the project root:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run Streamlit

```bash
streamlit run app/streamlit_app.py
```

No API keys are required for Phase 1.

## Environment Variables

Copy `.env.example` to `.env` if needed and fill in real values during later phases. Keep `.env` local.
