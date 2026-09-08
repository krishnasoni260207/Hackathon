# Rime Interruptible Study Assistant

A voice-first AI study assistant designed for natural, interruptible conversations.

The project focuses on a difficult voice interaction problem: **what happens when a user interrupts an AI assistant while it is speaking?**

The assistant uses speech recognition, an LLM, and Rime TTS to create a complete voice interaction. When the user starts speaking while the assistant is responding, the current playback is interrupted, obsolete work is treated as stale, and the new request becomes the active conversation request.

---

## 1. Problem

Traditional AI study assistants often behave like a request-and-response system:

1. User asks a question.
2. AI generates an answer.
3. AI speaks the answer.
4. User waits until the answer finishes.

This creates a poor experience when the user already knows what they want to say next.

For a voice-first study assistant, the user should be able to naturally interrupt the assistant, change the question, or correct the previous request.

The main engineering challenge in this project is therefore:

> **Stop obsolete assistant speech quickly and make the new user request authoritative.**

---

## 2. Target User

The target user is a student who wants to study through a natural voice conversation.

Example:

> User: "Explain photosynthesis."

The assistant starts answering.

While the assistant is speaking:

> User: "Actually, explain cellular respiration instead."

The assistant should:

- stop the previous audio,
- invalidate the old request,
- process the new request,
- generate the new answer,
- speak only the new answer.

The old response must not resume speaking after the interruption.

---

## 3. Key Voice Engineering Challenge

The project implements an interruptible voice pipeline:

```text
User speaks
    ↓
Audio recording
    ↓
Speech-to-Text
    ↓
LLM reasoning
    ↓
Rime TTS
    ↓
Audio playback
    ↓
User can interrupt
    ↓
Stop old playback
    ↓
Invalidate old request
    ↓
Process new request
    ↓
Speak only the new response
```

The important part is not simply generating speech.

The application must also maintain a consistent request state when an interruption occurs.

---

## 4. Features

- Voice-based study questions
- Speech-to-text input
- LLM-generated study responses
- Rime text-to-speech output
- Browser audio playback
- Real-time interruption handling
- Obsolete/stale response protection
- Conversation history
- Request state management
- Latency/interruption metrics
- Automated tests for interruption and stale responses
- Mock/fallback behavior for development/testing

---

## 5. Architecture

```text
                         ┌──────────────────────┐
                         │      Streamlit UI     │
                         │                       │
                         │ Microphone / Display  │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Voice Pipeline      │
                         │   / Voice Agent       │
                         └──────────┬────────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
             ┌───────────┐   ┌────────────┐   ┌─────────────┐
             │ Deepgram  │   │ OpenRouter │   │  Rime TTS   │
             │    STT    │   │    LLM     │   │    TTS      │
             └───────────┘   └────────────┘   └──────┬──────┘
                                                      │
                                                      ▼
                                            ┌──────────────────┐
                                            │  Audio Playback  │
                                            └────────┬─────────┘
                                                      │
                                                      ▼
                                              User hears answer

                     ┌──────────────────────────────┐
                     │ Interruption Controller       │
                     │                                │
                     │ Request IDs                    │
                     │ Cancellation                   │
                     │ Stale-response protection      │
                     └──────────────────────────────┘

                     ┌──────────────────────────────┐
                     │ Conversation State             │
                     │                                │
                     │ History                        │
                     │ Current request                │
                     │ Conversation management        │
                     └──────────────────────────────┘
```

---

## 6. Component Responsibilities

### Streamlit UI

The Streamlit application provides the user-facing interface.

It handles:

- microphone interaction,
- displaying conversation state,
- displaying pipeline status,
- receiving interruption events,
- triggering voice/text processing,
- playing generated audio.

Main entry point: `app/streamlit_app.py`

### Voice Agent

The voice agent coordinates the voice processing flow.

Main component: `backend/agents/voice_agent.py`

The agent connects:

```text
Audio
  ↓
STT
  ↓
LLM
  ↓
Rime TTS
```

### Speech-to-Text

Deepgram is used to convert recorded user audio into text.

Implementation: `backend/services/stt.py`

### LLM

The LLM generates the study assistant response.

Implementation: `backend/services/llm.py`

The application uses OpenRouter when running in real mode.

### Rime TTS

Rime converts the assistant's generated response into speech.

Implementation: `backend/services/rime_tts.py`

Rime is the primary text-to-speech provider in the intended demo flow.

### Interruption Controller

The interruption controller manages active requests and cancellation/stale-response protection.

Implementation: `backend/audio/interruption.py`

It is responsible for tracking which request is currently authoritative. When a new request begins, an older request must no longer be allowed to produce active user-facing speech.

### Playback

Audio playback state is managed by: `backend/audio/playback.py`

Browser-side recording and playback behavior is implemented through: `app/ui/voice_recorder.py`

### Conversation State

Conversation state and history are managed through:

- `backend/conversation/state.py`
- `backend/conversation/manager.py`

---

## 7. Interruption and Recovery

The most important interaction in this project is interruption.

**Normal flow:**

```text
User asks question
        ↓
STT transcribes question
        ↓
LLM generates response
        ↓
Rime generates speech
        ↓
Browser plays speech
```

**Interrupted flow:**

```text
Assistant is speaking
        ↓
User starts speaking
        ↓
Browser detects user speech
        ↓
Current playback is stopped
        ↓
Current request is interrupted
        ↓
Old request becomes stale
        ↓
New request is created
        ↓
New request is processed
        ↓
New response is generated
        ↓
Rime generates new speech
        ↓
Only new response is played
```

The application uses request identity/state to prevent obsolete responses from being played after a newer request has taken control.

---

## 8. Stale Response Protection

Interruption creates a race-condition problem.

For example:

```text
Request A
   ↓
LLM processing
   ↓
Rime processing
   ↓
User interrupts
   ↓
Request B
   ↓
Request B completes
```

Request A might still finish in the background. The application must not allow Request A to become the active spoken response after Request B has taken over. Therefore, the application checks request state before allowing results to proceed to user-facing playback.

The intended behavior is:

```text
Old request = stale
New request = authoritative
```

---

## 9. Third-Party Services

| Service    | Purpose        | Used By                        |
|------------|-----------------|---------------------------------|
| Rime       | Text-to-speech  | `backend/services/rime_tts.py` |
| Deepgram   | Speech-to-text  | `backend/services/stt.py`      |
| OpenRouter | LLM inference   | `backend/services/llm.py`      |

These services are accessed through their respective application service modules. API credentials are supplied through environment variables and are not stored in the source code.

---

## 10. Rime TTS Configuration

Rime is the primary TTS provider for the voice experience. The application sends text to the Rime TTS API and receives audio for playback.

**Exact Rime Configuration**

| Setting      | Value                                |
|--------------|----------------------------------------|
| Provider     | Rime                                  |
| Model ID     | `coda`                                |
| Speaker      | `celeste`                             |
| Language     | Configured through `RIME_LANG`        |
| Endpoint     | `https://users.rime.ai/v1/rime-tts`   |
| Audio format | WAV                                   |
| Transport    | HTTP REST API                         |

**Rime Implementation**

Rime integration is implemented in: `backend/services/rime_tts.py`

The service sends the generated assistant response to the Rime TTS endpoint and receives audio data for playback. The Rime model and speaker are configured through environment variables with the project defaults.

---

## 11. Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
RIME_API_KEY=your_rime_key
RIME_MODEL_ID=coda
RIME_SPEAKER=celeste
RIME_LANG=

DEEPGRAM_API_KEY=your_deepgram_key

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
```

**Important**

Never commit real API keys. The repository should contain `.env.example` with placeholder values, but the real `.env` must remain private.

---

## 12. Setup Instructions

### Requirements

The project uses Python and a virtual environment.

Python version used during development: **Python 3.13.5**

### Step 1: Clone the repository

```bash
git clone <repository-url>
cd rime-interruptible-study-assistant
```

### Step 2: Create a virtual environment

Windows:

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 4: Configure environment variables

Copy `.env.example` to `.env`. Then add your own API credentials.

Example:

```env
RIME_API_KEY=your_rime_key
DEEPGRAM_API_KEY=your_deepgram_key
OPENROUTER_API_KEY=your_openrouter_key
```

Do not commit `.env`.

---

## 13. Run the Application

Start the Streamlit application with:

```bash
python -m streamlit run app/streamlit_app.py
```

Streamlit will provide a local browser address. Open the displayed address in your browser and allow microphone access when requested.

---

## 14. Mock Mode

The project supports mock/fallback behavior when real API configuration is not available.

Mock mode is useful for:

- local development,
- testing,
- validating application flow without external API calls.

However, mock mode does not replace the real Rime integration for the hackathon demonstration. The intended voice demonstration uses the real Rime TTS path.

---

## 15. Testing

Run the complete automated test suite with:

```bash
python -m pytest -q
```

The test suite covers areas including:

- conversation state,
- interruption handling,
- recovery behavior,
- stale-response protection,
- Streamlit application behavior.

Important tests include:

- `tests/test_interruption.py`
- `tests/test_stale_response.py`
- `tests/test_recovery.py`
- `tests/test_conversation_state.py`
- `tests/test_streamlit_app.py`

---

## 16. Voice Acceptance Tests

### Test 1 — Normal Voice Flow

1. Start the application.
2. Ask a study question using the microphone.
3. Verify that the audio is transcribed.
4. Verify that the LLM generates an answer.
5. Verify that Rime generates speech.
6. Verify that the answer is played in the browser.

**Expected result:**

```text
User speech
→ STT
→ LLM
→ Rime
→ Audio playback
```

### Test 2 — Interruption

1. Ask a question.
2. Allow the assistant to begin speaking.
3. Start speaking while the assistant is speaking.
4. Verify that the current assistant audio stops.
5. Verify that the new request is processed.
6. Verify that the new response is spoken.

**Expected result:**

```text
Old response stops
        ↓
New request becomes active
        ↓
New response is spoken
```

### Test 3 — Stale Response

1. Start a request that produces a long response.
2. Interrupt it before it finishes.
3. Ask a different question.
4. Wait for the new response.
5. Verify that the old response does not resume speaking.

**Expected result:**

Only the current request is allowed to produce active user-facing speech.

---

## 17. Failure Behavior

The application depends on multiple external services, so failures can occur at different stages.

### Microphone / Audio Failure

If browser microphone access is unavailable, the voice input cannot be recorded.

The user should grant microphone permission to the browser and retry.

### Speech-to-Text Failure

If speech recognition fails or no usable transcript is returned, the request cannot continue through the normal voice pipeline.

The application reports the pipeline failure rather than generating a response from nonexistent input.

### LLM Failure

If the LLM request fails, the application reports the pipeline error and does not attempt to present a normal assistant response.

### Rime TTS Failure

If Rime TTS fails, the application cannot produce the normal Rime spoken response.

The error is surfaced through the application pipeline rather than silently presenting an incorrect audio result.

### Playback Failure

If browser audio playback fails, the response may be generated successfully but cannot be heard through the browser.

The playback state is managed separately from response generation.

### User Interruption

When the user interrupts the assistant:

- Current playback is stopped.
- The active request is interrupted.
- A new request becomes authoritative.
- Obsolete results are prevented from becoming active playback.
- The new request continues through the pipeline.

### Stale Results

A previous request may still finish processing after the user has interrupted it.

Those results must not become the active spoken response after a newer request has taken control.

---

## 18. Known Limitations

The current application has several practical limitations:

- Voice interaction depends on browser microphone permissions.
- Real STT, LLM, and Rime TTS operation requires network connectivity.
- External API availability can affect the voice pipeline.
- Browser audio playback behavior can vary between environments.
- Interruption timing depends partly on browser audio and microphone event timing.
- Mock mode does not represent the full real-world Rime voice experience.
- The application is designed primarily as a hackathon demonstration rather than a production-scale multi-user deployment.

---

## 19. Failure and Recovery Philosophy

The application treats an interruption as a change in conversational authority.

The important rule is:

```text
Newest valid request
        >
Older interrupted request
```

The system therefore attempts to maintain consistency between:

- what the user requested,
- what the application considers active,
- what the user actually heard.

This is important because simply stopping browser playback is not enough. If an old model or TTS request finishes later, its result must not be allowed to resume as if it were still current.

---

## 20. Evidence and Reproducibility

The repository contains automated tests and evidence files related to interruption and latency.

Relevant locations include:

- `tests/`
- `evidence/`

Evidence files include:

- `evidence/interruption_results.csv`
- `evidence/latency_results.csv`

The test suite can be reproduced with:

```bash
python -m pytest -q
```

Performance claims should be based on recorded/reproducible measurements rather than unsupported estimates.

---

## 21. Project Structure

```text
rime-interruptible-study-assistant/
│
├── app/
│   ├── streamlit_app.py
│   └── ui/
│       ├── __init__.py
│       ├── components.py
│       ├── conversation_view.py
│       ├── pipeline_view.py
│       ├── status_view.py
│       └── voice_recorder.py
│
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── voice_agent.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py
│   │   ├── stt.py
│   │   └── rime_tts.py
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── interruption.py
│   │   └── playback.py
│   │
│   ├── conversation/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   └── manager.py
│   │
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── interruption_metrics.py
│   │
│   ├── __init__.py
│   └── main.py
│
├── tests/
│   ├── test_conversation_state.py
│   ├── test_interruption.py
│   ├── test_recovery.py
│   ├── test_stale_response.py
│   └── test_streamlit_app.py
│
├── docs/
│   ├── API_SETUP.md
│   ├── ARCHITECTURE.md
│   ├── DEMO_SCRIPT.md
│   ├── TECHNOLOGY.md
│   └── TESTING.md
│
├── evidence/
│   ├── interruption_results.csv
│   └── latency_results.csv
│
├── .env.example
├── .gitignore
├── CHANGELOG
├── README.md
├── requirements.txt
```

---

## 22. Technology Stack

| Technology | Purpose                     |
|------------|-------------------------------|
| Python     | Application/backend logic    |
| Streamlit  | User interface                |
| Deepgram   | Speech-to-text                |
| OpenRouter | LLM inference                 |
| Rime       | Text-to-speech                |
| HTTPX      | HTTP API communication        |
| pytest     | Automated testing             |

---

## 23. Why Rime Is Important to This Project

Rime is not included as an incidental integration. Rime is part of the primary voice pipeline:

```text
User speech
    ↓
Deepgram
    ↓
LLM
    ↓
Rime
    ↓
Spoken response
```

The application's voice experience depends on generating and playing synthesized speech.

The interruption challenge is especially important because stopping playback is only one part of the problem. The application must also ensure that an obsolete Rime response cannot become active after the user has moved on to a new request.

---

## 24. Demo Scenario

A recommended demonstration flow is:

**Step 1**
User asks: "Explain photosynthesis."

**Step 2**
The application transcribes the question.

**Step 3**
The LLM generates a study explanation.

**Step 4**
Rime generates the spoken response.

**Step 5**
The assistant begins speaking.

**Step 6**
The user interrupts: "Actually, explain cellular respiration."

**Step 7**
The current assistant audio stops.

**Step 8**
The new request becomes authoritative.

**Step 9**
The new answer is generated and synthesized.

**Step 10**
Only the new answer is spoken.

This demonstrates the core engineering challenge of the project.

---

## 25. Security

API credentials must never be committed to the repository.

Use `.env` for real credentials. Use `.env.example` for safe placeholder configuration.

Example:

```env
RIME_API_KEY=your_rime_key
DEEPGRAM_API_KEY=your_deepgram_key
OPENROUTER_API_KEY=your_openrouter_key
```

Never put real API keys in:

- README.md
- source code
- GitHub commits
- screenshots
- documentation
- test fixtures

---

## 26. Limitations and Future Improvements

Possible future improvements include:

- lower interruption latency,
- more sophisticated voice activity detection,
- improved streaming TTS,
- stronger cancellation of background work,
- production-grade multi-user session management,
- improved browser audio handling,
- more extensive automated end-to-end voice testing.

These are future improvements and are not claims about functionality that is currently implemented.

---

## 27. Hackathon Requirements Checklist

This README explicitly documents the required project information.

**General README Requirements**

- [x] Setup instructions
- [x] Architecture
- [x] Third-party services
- [x] Known limitations
- [x] Failure behavior

**Exact Rime Configuration**

- [x] Rime model ID
- [x] Rime speaker
- [x] Rime language configuration
- [x] Rime endpoint
- [x] Rime audio format
- [x] Rime transport

**Security**

- [x] No API keys included in README
- [x] Environment variables documented
- [x] `.env` should remain private
- [x] `.env.example` uses placeholders

**Voice Engineering**

- [x] Normal voice flow documented
- [x] Interruption flow documented
- [x] Stale-response behavior documented
- [x] Failure behavior documented
- [x] Recovery behavior documented

---

## 28. Quick Start

For a quick local run:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configure `.env`, then run:

```bash
python -m streamlit run app/streamlit_app.py
```

Run tests:

```bash
python -m pytest -q
```

---

## License

This project was created as part of a Rime voice AI hackathon submission.
