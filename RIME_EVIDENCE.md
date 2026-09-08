# Rime Voice Engineering Evidence

## 1. Hard Voice-Engineering Claim

This project uses Rime as the primary speech-output provider and focuses on interruptible voice interaction.

The main hard voice-engineering problem is:

> When the user interrupts the assistant while it is speaking, the current speech must stop promptly, obsolete work must not continue speaking, and the new request must become the active conversation state.

The application handles interruption, cancellation, stale-response protection, playback state, and recovery.

## 2. Rime Integration

Rime is used as the primary TTS provider for assistant responses.

### Rime configuration

| Setting | Value |
|---|---|
| Provider | Rime |
| Endpoint | `https://users.rime.ai/v1/rime-tts` |
| Model ID | `coda` |
| Speaker | `celeste` |
| Audio format | WAV |
| Transport | HTTP REST API |

The application sends generated assistant text to Rime and receives audio for playback.

API credentials are stored in environment variables and are not committed to the repository.

## 3. Acceptance Test

The acceptance test verifies that the assistant can recover correctly when the user interrupts an ongoing response.

### Test scenario

1. User asks a question.
2. Assistant begins processing and speaking the answer.
3. User interrupts while the assistant response is active.
4. Current playback is stopped.
5. The previous request is marked obsolete.
6. The user's new input becomes the active request.
7. The new request is processed.
8. The old response must not resume speaking.
9. Only the current response is played.

### Expected result

The user hears the new response rather than the obsolete response.

## 4. Interruption and Recovery Procedure

The application uses an interruption controller to track request IDs and active work.

When a new request starts, the application creates a new request ID.

The active request is checked before results are used for playback.

If the user interrupts the assistant:

- browser audio playback is stopped;
- the active request is invalidated;
- obsolete work is prevented from becoming the current spoken response;
- the new request becomes the active conversation request;
- only the current valid response is allowed to reach playback.

This prevents stale assistant responses from being spoken after an interruption.

## 5. Stale Response Protection

The system uses request identity to distinguish current work from obsolete work.

Before assistant audio is played, the result is checked against the current request state.

If the result belongs to an obsolete request, it is discarded instead of being played.

This is important because stopping browser playback alone is not sufficient: an older asynchronous response could otherwise finish later and start playing again.

## 6. Automated Test Evidence

The project includes automated tests for:

- conversation state
- interruption behavior
- recovery behavior
- stale responses
- Streamlit pipeline behavior
- voice-agent behavior

The final local verification reported:

```text
26 passed