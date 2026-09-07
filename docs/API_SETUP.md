# API Setup

Create local API credentials in `.env` when future phases need them.

Expected variables:

```env
BACKEND_MODE=mock

RIME_API_KEY=
OPENAI_API_KEY=

LLM_MODEL=gpt-6-astra
LLM_MAX_OUTPUT_TOKENS=600
STT_MODEL=gpt-transcribe

RIME_SPEAKER=celeste
RIME_MODEL_ID=coda
RIME_AUDIO_FORMAT=audio/wav

DEEPGRAM_API_KEY=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
```

Do not commit `.env`.

`BACKEND_MODE=mock` runs without keys and returns visible test output.
`BACKEND_MODE=real` calls OpenAI for LLM/STT and Rime for TTS.
LiveKit and Deepgram are still reserved for later realtime voice phases.
