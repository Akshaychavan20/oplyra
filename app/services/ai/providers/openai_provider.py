"""OpenAI Chat Completions provider (also base pattern for compatible APIs)."""
from __future__ import annotations

import time
from typing import List, Optional

from app.services.ai.base import BaseProvider
from app.services.ai.catalog import MODEL_CATALOG, resolve_default_model
from app.services.ai.http_util import approx_tokens, mock_response_text, post_json
from app.services.ai.types import AIRequest, AIResponse, ModelSpec, ProviderId


class OpenAIProvider(BaseProvider):
    provider_id = ProviderId.OPENAI
    display_name = 'OpenAI'
    base_url = 'https://api.openai.com/v1'

    def list_models(self) -> List[ModelSpec]:
        return [m for m in MODEL_CATALOG if m.provider == ProviderId.OPENAI and m.enabled]

    def generate_text(self, request: AIRequest) -> AIResponse:
        model = request.model or resolve_default_model(ProviderId.OPENAI)
        started = time.time()

        if self.is_mock_key():
            text = mock_response_text('openai', model, request.prompt)
            inp = approx_tokens(request.prompt)
            out = approx_tokens(text)
            return AIResponse(
                text=text,
                provider=self.provider_id.value,
                model=model,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=inp + out,
                latency_ms=int((time.time() - started) * 1000),
            )

        messages = []
        if request.system_instruction:
            messages.append({'role': 'system', 'content': request.system_instruction})
        messages.append({'role': 'user', 'content': request.prompt})

        payload = {
            'model': model,
            'messages': messages,
        }
        if request.temperature is not None:
            payload['temperature'] = request.temperature
        if request.max_tokens is not None:
            payload['max_tokens'] = request.max_tokens
        if request.json_mode:
            payload['response_format'] = {'type': 'json_object'}

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        body, latency_ms = post_json(
            f'{self.base_url.rstrip("/")}/chat/completions',
            headers=headers,
            payload=payload,
            timeout=request.timeout or 60.0,
        )

        choice = (body.get('choices') or [{}])[0]
        text = (choice.get('message') or {}).get('content') or ''
        usage = body.get('usage') or {}
        input_tokens = int(usage.get('prompt_tokens') or approx_tokens(request.prompt))
        output_tokens = int(usage.get('completion_tokens') or approx_tokens(text))
        total_tokens = int(usage.get('total_tokens') or (input_tokens + output_tokens))

        return AIResponse(
            text=text,
            provider=self.provider_id.value,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms or int((time.time() - started) * 1000),
            finish_reason=choice.get('finish_reason'),
            raw={'id': body.get('id')},
        )


class OpenAICompatibleProvider(OpenAIProvider):
    """Generic OpenAI-compatible endpoint (OpenRouter, Together, local, etc.)."""

    provider_id = ProviderId.OPENAI_COMPATIBLE
    display_name = 'OpenAI Compatible'

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        if base_url:
            self.base_url = base_url

    def list_models(self) -> List[ModelSpec]:
        return []
