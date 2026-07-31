"""Google Gemini provider adapter."""
from __future__ import annotations

import time
from typing import List, Optional

from app.services.ai.base import BaseProvider
from app.services.ai.catalog import MODEL_CATALOG, resolve_default_model
from app.services.ai.http_util import approx_tokens, mock_response_text
from app.services.ai.types import AIRequest, AIResponse, ModelSpec, ProviderId


class GeminiProvider(BaseProvider):
    provider_id = ProviderId.GEMINI
    display_name = 'Google Gemini'

    def list_models(self) -> List[ModelSpec]:
        return [m for m in MODEL_CATALOG if m.provider == ProviderId.GEMINI and m.enabled]

    def generate_text(self, request: AIRequest) -> AIResponse:
        model = request.model or resolve_default_model(ProviderId.GEMINI)
        started = time.time()

        if self.is_mock_key():
            text = mock_response_text('gemini', model, request.prompt)
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

        try:
            from google import genai
            from google.genai import types
            from google.genai.errors import APIError
        except ImportError as e:
            raise RuntimeError('google-genai package is not installed') from e

        max_retries = 4
        delay = 2.0
        last_err: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=self.api_key)
                config_kwargs = {}
                if request.system_instruction:
                    config_kwargs['system_instruction'] = request.system_instruction
                if request.temperature is not None:
                    config_kwargs['temperature'] = request.temperature
                if request.max_tokens is not None:
                    config_kwargs['max_output_tokens'] = request.max_tokens
                config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

                response = client.models.generate_content(
                    model=model,
                    contents=request.prompt,
                    config=config,
                )
                if not response or not response.text:
                    raise ValueError('Empty response from Gemini')

                input_tokens = 0
                output_tokens = 0
                total_tokens = 0
                if response.usage_metadata:
                    input_tokens = response.usage_metadata.prompt_token_count or 0
                    output_tokens = response.usage_metadata.candidates_token_count or 0
                    total_tokens = response.usage_metadata.total_token_count or (input_tokens + output_tokens)
                else:
                    input_tokens = approx_tokens(request.prompt)
                    output_tokens = approx_tokens(response.text)
                    total_tokens = input_tokens + output_tokens

                return AIResponse(
                    text=response.text,
                    provider=self.provider_id.value,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=int((time.time() - started) * 1000),
                    retry_count=attempt,
                )
            except APIError as e:
                last_err = e
                if getattr(e, 'code', None) in (503, 429) and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f'Gemini API Error: {e}') from e
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(f'Gemini connection error: {e}') from e

        raise RuntimeError(str(last_err or 'Gemini request failed'))
