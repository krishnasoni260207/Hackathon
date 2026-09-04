from __future__ import annotations

import json


PROJECT_NAME = "Interruptible Study Assistant"
PHASE = "Phase 1"


def get_phase_status() -> dict[str, object]:
    return {
        "project": PROJECT_NAME,
        "phase": PHASE,
        "implemented": ["project structure", "Streamlit UI shell"],
        "not_implemented": [
            "realtime STT",
            "LLM calls",
            "Rime TTS calls",
            "LiveKit connection",
            "audio playback",
            "interruption and recovery logic",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(get_phase_status(), indent=2))
