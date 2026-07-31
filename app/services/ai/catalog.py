"""Catalog of known models and default routing preferences."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.services.ai.types import ModelSpec, ProviderId, TaskType


MODEL_CATALOG: List[ModelSpec] = [
    # Gemini
    ModelSpec(ProviderId.GEMINI, 'gemini-2.5-flash', 'Gemini 2.5 Flash',
              supports_vision=True, input_cost_per_m=0.075, output_cost_per_m=0.30),
    ModelSpec(ProviderId.GEMINI, 'gemini-2.5-pro', 'Gemini 2.5 Pro',
              supports_vision=True, supports_tools=True, input_cost_per_m=1.25, output_cost_per_m=5.0),
    ModelSpec(ProviderId.GEMINI, 'gemini-1.5-flash', 'Gemini 1.5 Flash',
              supports_vision=True, input_cost_per_m=0.075, output_cost_per_m=0.30),
    ModelSpec(ProviderId.GEMINI, 'gemini-1.5-pro', 'Gemini 1.5 Pro',
              supports_vision=True, input_cost_per_m=1.25, output_cost_per_m=5.0),
    # OpenAI
    ModelSpec(ProviderId.OPENAI, 'gpt-4o', 'GPT-4o',
              supports_vision=True, supports_tools=True, input_cost_per_m=2.50, output_cost_per_m=10.0),
    ModelSpec(ProviderId.OPENAI, 'gpt-4o-mini', 'GPT-4o Mini',
              supports_vision=True, supports_tools=True, input_cost_per_m=0.15, output_cost_per_m=0.60),
    ModelSpec(ProviderId.OPENAI, 'gpt-4.1', 'GPT-4.1',
              supports_tools=True, input_cost_per_m=2.0, output_cost_per_m=8.0),
    # Anthropic
    ModelSpec(ProviderId.ANTHROPIC, 'claude-sonnet-4-20250514', 'Claude Sonnet 4',
              supports_vision=True, supports_tools=True, input_cost_per_m=3.0, output_cost_per_m=15.0),
    ModelSpec(ProviderId.ANTHROPIC, 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet',
              supports_vision=True, supports_tools=True, input_cost_per_m=3.0, output_cost_per_m=15.0),
    ModelSpec(ProviderId.ANTHROPIC, 'claude-3-5-haiku-20241022', 'Claude 3.5 Haiku',
              supports_tools=True, input_cost_per_m=0.80, output_cost_per_m=4.0),
    # DeepSeek
    ModelSpec(ProviderId.DEEPSEEK, 'deepseek-chat', 'DeepSeek Chat',
              supports_tools=True, input_cost_per_m=0.14, output_cost_per_m=0.28),
    ModelSpec(ProviderId.DEEPSEEK, 'deepseek-reasoner', 'DeepSeek Reasoner',
              input_cost_per_m=0.55, output_cost_per_m=2.19),
]

# Default model per provider when only provider is selected
DEFAULT_MODELS: Dict[ProviderId, str] = {
    ProviderId.GEMINI: 'gemini-2.5-flash',
    ProviderId.OPENAI: 'gpt-4o-mini',
    ProviderId.ANTHROPIC: 'claude-3-5-sonnet-20241022',
    ProviderId.DEEPSEEK: 'deepseek-chat',
}

# Task → preferred provider chain (first available wins)
DEFAULT_ROUTING: Dict[TaskType, List[ProviderId]] = {
    TaskType.LONG_WRITING: [ProviderId.ANTHROPIC, ProviderId.OPENAI, ProviderId.GEMINI],
    TaskType.BLOG: [ProviderId.ANTHROPIC, ProviderId.OPENAI, ProviderId.GEMINI],
    TaskType.MARKETING_COPY: [ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.GEMINI],
    TaskType.AD_COPY: [ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.GEMINI],
    TaskType.EMAIL: [ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.GEMINI],
    TaskType.SOCIAL: [ProviderId.OPENAI, ProviderId.GEMINI, ProviderId.DEEPSEEK],
    TaskType.SEO: [ProviderId.OPENAI, ProviderId.GEMINI, ProviderId.ANTHROPIC],
    TaskType.CODING: [ProviderId.ANTHROPIC, ProviderId.OPENAI, ProviderId.DEEPSEEK],
    TaskType.IMAGE_ANALYSIS: [ProviderId.GEMINI, ProviderId.OPENAI, ProviderId.ANTHROPIC],
    TaskType.PDF_ANALYSIS: [ProviderId.GEMINI, ProviderId.ANTHROPIC, ProviderId.OPENAI],
    TaskType.FAST_CHEAP: [ProviderId.DEEPSEEK, ProviderId.GEMINI, ProviderId.OPENAI],
    TaskType.GENERAL_CHAT: [ProviderId.OPENAI, ProviderId.GEMINI, ProviderId.ANTHROPIC, ProviderId.DEEPSEEK],
    TaskType.UNKNOWN: [ProviderId.GEMINI, ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.DEEPSEEK],
}

# Global fallback chain when a provider fails mid-request
FALLBACK_CHAIN: List[ProviderId] = [
    ProviderId.OPENAI,
    ProviderId.ANTHROPIC,
    ProviderId.GEMINI,
    ProviderId.DEEPSEEK,
]

# User-facing picker labels
UI_PROVIDER_OPTIONS = [
    {'id': 'auto', 'label': 'Auto (Recommended)', 'provider': 'auto'},
    {'id': 'openai', 'label': 'GPT', 'provider': 'openai'},
    {'id': 'anthropic', 'label': 'Claude', 'provider': 'anthropic'},
    {'id': 'gemini', 'label': 'Gemini', 'provider': 'gemini'},
    {'id': 'deepseek', 'label': 'DeepSeek', 'provider': 'deepseek'},
]


def find_model(model_id: str) -> Optional[ModelSpec]:
    if not model_id:
        return None
    key = model_id.strip().lower()
    for spec in MODEL_CATALOG:
        if spec.model_id.lower() == key:
            return spec
    return None


def infer_provider_from_model(model_id: Optional[str]) -> Optional[ProviderId]:
    spec = find_model(model_id or '')
    if spec:
        return spec.provider
    if not model_id:
        return None
    m = model_id.lower()
    if m.startswith('gemini') or m.startswith('models/gemini'):
        return ProviderId.GEMINI
    if m.startswith('gpt') or m.startswith('o1') or m.startswith('o3'):
        return ProviderId.OPENAI
    if m.startswith('claude'):
        return ProviderId.ANTHROPIC
    if m.startswith('deepseek'):
        return ProviderId.DEEPSEEK
    if m in ('auto',):
        return ProviderId.AUTO
    return None


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    spec = find_model(model_id)
    if not spec:
        # Legacy Gemini-style heuristic
        input_rate = 0.075 / 1_000_000
        output_rate = 0.30 / 1_000_000
        if 'pro' in (model_id or '').lower():
            input_rate = 1.25 / 1_000_000
            output_rate = 5.00 / 1_000_000
        return (input_tokens * input_rate) + (output_tokens * output_rate)
    return (
        (input_tokens * spec.input_cost_per_m / 1_000_000)
        + (output_tokens * spec.output_cost_per_m / 1_000_000)
    )


def resolve_default_model(provider: ProviderId) -> str:
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS[ProviderId.GEMINI])
