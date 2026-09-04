from __future__ import annotations


class LLMService:
    def generate_response(self, _prompt: str) -> str:
        raise NotImplementedError("LLM calls are not implemented in Phase 1.")
