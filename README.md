# Interruptible Study Assistant

A voice-first study assistant for university students.

The target user is a university student who wants to ask study questions out loud and receive spoken explanations. The main product problem is making an AI assistant feel natural during study sessions, especially when the student changes direction while the assistant is speaking.

The eventual goal is an interruptible assistant: when the AI is speaking, the student can interrupt naturally, the old response is stopped or marked invalid, and the new request is handled instead.

## Phase 1 Status

Phase 1 sets up the project structure, dependencies, environment placeholders, documentation, tests, and a runnable Streamlit UI.

Implemented:

- Project folders and Python packages.
- Voice-bot styled Streamlit UI with example study conversation.
- Placeholder status and voice controls.
- Voice input panel for typed text or recorded audio.
- Mock backend output for Speech-to-Text, LLM, and Rime TTS.
- Real API hooks for OpenAI LLM/STT and Rime TTS when configured.
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

From the project root:

```bash
streamlit run app/streamlit_app.py
```

### Voice UI flow

1. Click **Start session** to initialize the voice agent.
2. Click **Record** to capture microphone audio.
3. Click **Submit recording** to stop capture and run STT → LLM → TTS automatically.
4. Listen to the generated speech in the Output panel (autoplay enabled).
5. Click **Record** again for another turn, or **End session** when finished.

Typed questions are available under **Type a question instead**.

## Environment Variables

Copy `.env.example` to `.env` if needed and fill in real values. Keep `.env` local.

`BACKEND_MODE=mock` runs without network calls and returns predictable test output with silent WAV audio.
`BACKEND_MODE=real` calls OpenAI for STT/LLM and Rime for human-like TTS. Requires `OPENAI_API_KEY` and `RIME_API_KEY`.
