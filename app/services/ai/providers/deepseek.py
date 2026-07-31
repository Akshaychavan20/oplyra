"""DeepSeek provider — OpenAI-compatible API."""
from __future__ import annotations

from typing import List

from app.services.ai.catalog import MODEL_CATALOG
from app.services.ai.providers.openai_provider import OpenAIProvider
from app.services.ai.types import ModelSpec, ProviderId


class DeepSeekProvider(OpenAIProvider):
    provider_id = ProviderId.DEEPSEEK
    display_name = 'DeepSeek'
    base_url = 'https://api.deepseek.com'

    def list_models(self) -> List[ModelSpec]:
        return [m for m in MODEL_CATALOG if m.provider == ProviderId.DEEPSEEK and m.enabled]
