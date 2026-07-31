"""Prompt pipeline hooks — pre/post processing without provider leakage."""
from __future__ import annotations

from typing import Optional

from app.services.ai.types import AIRequest


class PromptPipeline:
    """
    Extensible prompt pipeline.

    Stages: safety → context injection → system prompt merge → execute → format
    Memory / RAG hooks can plug in here later without changing providers.
    """

    def preprocess(self, request: AIRequest) -> AIRequest:
        prompt = (request.prompt or '').strip()
        if not prompt:
            raise ValueError('Prompt cannot be empty.')

        # Basic safety: strip null bytes / extreme length guard
        prompt = prompt.replace('\x00', '')
        if len(prompt) > 200_000:
            raise ValueError('Prompt exceeds maximum allowed length.')

        system = request.system_instruction
        if system:
            system = system.strip()

        # Inject soft product identity when no system prompt provided
        if not system:
            system = (
                'You are Oplyra AI, an expert marketing operating system assistant. '
                'Be clear, actionable, and brand-safe.'
            )

        request.prompt = prompt
        request.system_instruction = system
        return request

    def postprocess(self, text: str) -> str:
        if not text:
            return text
        # Strip accidental markdown fences wrapping entire output
        stripped = text.strip()
        if stripped.startswith('```') and stripped.endswith('```'):
            lines = stripped.split('\n')
            if len(lines) >= 2:
                inner = '\n'.join(lines[1:-1])
                if lines[0].startswith('```markdown') or lines[0] == '```':
                    return inner.strip()
        return text
