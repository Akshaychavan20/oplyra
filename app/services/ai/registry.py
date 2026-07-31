"""Provider registry — discovers and resolves enabled providers."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from flask import current_app

from app.services.ai.base import BaseProvider
from app.services.ai.catalog import MODEL_CATALOG, UI_PROVIDER_OPTIONS, find_model
from app.services.ai.providers import (
    AnthropicProvider,
    DeepSeekProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
)
from app.services.ai.types import ModelSpec, ProviderId


def _cfg(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if current_app:
            val = current_app.config.get(key)
            if val:
                return val
    except RuntimeError:
        pass
    return os.environ.get(key, default)


def _flag_enabled(env_key: str, default: bool = True) -> bool:
    raw = _cfg(env_key)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


class ProviderRegistry:
    """Singleton-style registry of provider adapters."""

    _instance: Optional['ProviderRegistry'] = None

    def __init__(self):
        self._providers: Dict[ProviderId, BaseProvider] = {}
        self.reload()

    @classmethod
    def instance(cls) -> 'ProviderRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def reload(self) -> None:
        self._providers = {}

        gemini = GeminiProvider(api_key=_cfg('GEMINI_API_KEY'))
        gemini.set_enabled(_flag_enabled('AI_ENABLE_GEMINI', True))
        self._providers[ProviderId.GEMINI] = gemini

        openai = OpenAIProvider(api_key=_cfg('OPENAI_API_KEY'))
        openai.set_enabled(_flag_enabled('AI_ENABLE_OPENAI', True))
        self._providers[ProviderId.OPENAI] = openai

        anthropic = AnthropicProvider(api_key=_cfg('ANTHROPIC_API_KEY'))
        anthropic.set_enabled(_flag_enabled('AI_ENABLE_ANTHROPIC', True))
        self._providers[ProviderId.ANTHROPIC] = anthropic

        deepseek = DeepSeekProvider(api_key=_cfg('DEEPSEEK_API_KEY'))
        deepseek.set_enabled(_flag_enabled('AI_ENABLE_DEEPSEEK', True))
        self._providers[ProviderId.DEEPSEEK] = deepseek

        # Future-ready OpenAI-compatible slot (disabled unless configured)
        compat_key = _cfg('OPENAI_COMPATIBLE_API_KEY')
        compat_url = _cfg('OPENAI_COMPATIBLE_BASE_URL')
        if compat_key and compat_url:
            compat = OpenAICompatibleProvider(api_key=compat_key, base_url=compat_url)
            compat.set_enabled(_flag_enabled('AI_ENABLE_OPENAI_COMPATIBLE', True))
            self._providers[ProviderId.OPENAI_COMPATIBLE] = compat

    def get(self, provider_id: ProviderId) -> Optional[BaseProvider]:
        return self._providers.get(provider_id)

    def get_enabled(self) -> List[BaseProvider]:
        return [p for p in self._providers.values() if p.enabled]

    def list_providers(self) -> List[Dict]:
        rows = []
        for pid, provider in self._providers.items():
            rows.append({
                'id': pid.value,
                'name': provider.display_name,
                'enabled': provider.enabled,
                'configured': provider.is_configured(),
                'mock': provider.is_mock_key(),
                'models': [m.model_id for m in provider.list_models()],
            })
        return rows

    def list_models(self, enabled_only: bool = True) -> List[ModelSpec]:
        out = []
        for spec in MODEL_CATALOG:
            if enabled_only:
                provider = self.get(spec.provider)
                if not provider or not provider.enabled:
                    continue
            if spec.enabled:
                out.append(spec)
        return out

    def ui_options(self) -> List[Dict]:
        enabled_ids = {p.provider_id.value for p in self.get_enabled()}
        options = []
        for opt in UI_PROVIDER_OPTIONS:
            if opt['id'] == 'auto' or opt['provider'] in enabled_ids:
                options.append(dict(opt))
        return options

    def resolve_model_provider(self, model_id: Optional[str]) -> Optional[BaseProvider]:
        if not model_id:
            return None
        spec = find_model(model_id)
        if not spec:
            return None
        return self.get(spec.provider)
