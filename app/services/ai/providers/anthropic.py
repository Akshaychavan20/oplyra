"""Anthropic Claude Messages API provider."""
from __future__ import annotations

import time
from typing import List

from app.services.ai.base import BaseProvider
from app.services.ai.catalog import MODEL_CATALOG, resolve_default_model
from app.services.ai.http_util import approx_tokens, mock_response_text, post_json
from app.services.ai.types import AIRequest, AIResponse, ModelSpec, ProviderId


class AnthropicProvider(BaseProvider):
    provider_id = ProviderId.ANTHROPIC
    display_name = 'Anthropic Claude'
    base_url = 'https://api.anthropic.com/v1'
    api_version = '2023-06-01'

    def list_models(self) -> List[ModelSpec]:
        return [m for m in MODEL_CATALOG if m.provider == ProviderId.ANTHROPIC and m.enabled]

    def generate_text(self, request: AIRequest) -> AIResponse:
        model = request.model or resolve_default_model(ProviderId.ANTHROPIC)
        started = time.time()

        if self.is_mock_key():
            text = mock_response_text('anthropic', model, request.prompt)
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

        payload = {
            'model': model,
            'max_tokens': request.max_tokens or 4096,
            'messages': [{'role': 'user', 'content': request.prompt}],
        }
        if request.system_instruction:
            payload['system'] = request.system_instruction
        if request.temperature is not None:
            payload['temperature'] = request.temperature

        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': self.api_version,
            'Content-Type': 'application/json',
        }
        body, latency_ms = post_json(
            f'{self.base_url.rstrip("/")}/messages',
            headers=headers,
            payload=payload,
            timeout=request.timeout or 90.0,
        )

        blocks = body.get('content') or []
        text_parts = [b.get('text', '') for b in blocks if b.get('type') == 'text']
        text = '\n'.join(text_parts)
        usage = body.get('usage') or {}
        input_tokens = int(usage.get('input_tokens') or approx_tokens(request.prompt))
        output_tokens = int(usage.get('output_tokens') or approx_tokens(text))

        return AIResponse(
            text=text,
            provider=self.provider_id.value,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms or int((time.time() - started) * 1000),
            finish_reason=body.get('stop_reason'),
            raw={'id': body.get('id')},
        )
