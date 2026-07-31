"""Task classification and provider routing."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from app.services.ai.catalog import (
    DEFAULT_ROUTING,
    FALLBACK_CHAIN,
    infer_provider_from_model,
    resolve_default_model,
)
from app.services.ai.registry import ProviderRegistry
from app.services.ai.types import AIRequest, ProviderId, TaskType


# Keyword heuristics for Auto mode (admin DB rules can override later)
_TASK_PATTERNS = [
    (TaskType.PDF_ANALYSIS, re.compile(r'\b(pdf|document analysis|extract from (doc|pdf))\b', re.I)),
    (TaskType.IMAGE_ANALYSIS, re.compile(r'\b(image|screenshot|vision|analyze (this )?photo)\b', re.I)),
    (TaskType.CODING, re.compile(r'\b(code|python|javascript|refactor|bug|function|api endpoint)\b', re.I)),
    (TaskType.SEO, re.compile(r'\b(seo|meta description|keyword density|search ranking)\b', re.I)),
    (TaskType.LONG_WRITING, re.compile(r'\b(long[- ]form|whitepaper|ebook|detailed article)\b', re.I)),
    (TaskType.BLOG, re.compile(r'\b(blog|article|newsletter post)\b', re.I)),
    (TaskType.AD_COPY, re.compile(r'\b(ad copy|advertisement|paid ads|facebook ad|google ad)\b', re.I)),
    (TaskType.EMAIL, re.compile(r'\b(email|subject line|drip sequence)\b', re.I)),
    (TaskType.SOCIAL, re.compile(r'\b(social|instagram|linkedin|tweet|facebook post|carousel)\b', re.I)),
    (TaskType.MARKETING_COPY, re.compile(r'\b(marketing|landing page|cta|conversion|brand voice)\b', re.I)),
    (TaskType.FAST_CHEAP, re.compile(r'\b(quick|short|summarize|tl;dr|bullet)\b', re.I)),
]


class TaskRouter:
    """
    Classifies tasks and selects provider/model.

    Custom routing_rules from DB (when present) override DEFAULT_ROUTING.
    """

    def __init__(self, registry: Optional[ProviderRegistry] = None, custom_rules: Optional[Dict] = None):
        self.registry = registry or ProviderRegistry.instance()
        self.custom_rules = custom_rules or {}

    def classify(self, prompt: str, explicit: Optional[TaskType] = None) -> TaskType:
        if explicit and explicit != TaskType.UNKNOWN:
            return explicit
        text = prompt or ''
        for task, pattern in _TASK_PATTERNS:
            if pattern.search(text):
                return task
        if len(text.split()) > 400:
            return TaskType.LONG_WRITING
        return TaskType.GENERAL_CHAT

    def preferred_chain(self, task: TaskType) -> List[ProviderId]:
        if task.value in self.custom_rules:
            raw = self.custom_rules[task.value]
            chain = []
            for item in raw:
                try:
                    chain.append(ProviderId(item) if not isinstance(item, ProviderId) else item)
                except ValueError:
                    continue
            if chain:
                return chain
        return list(DEFAULT_ROUTING.get(task, DEFAULT_ROUTING[TaskType.UNKNOWN]))

    def select(self, request: AIRequest) -> tuple[ProviderId, str]:
        """
        Returns (provider_id, model_id) for an AIRequest.
        Respects explicit provider/model; otherwise uses Auto routing.
        """
        # Explicit model string wins
        if request.model and request.model.lower() not in ('auto',):
            inferred = infer_provider_from_model(request.model)
            if inferred and inferred != ProviderId.AUTO:
                provider = self.registry.get(inferred)
                if provider and provider.enabled:
                    return inferred, request.model
            # Unknown model string — try gemini legacy path
            gemini = self.registry.get(ProviderId.GEMINI)
            if gemini and gemini.enabled:
                return ProviderId.GEMINI, request.model

        provider_pref = request.provider
        if isinstance(provider_pref, str):
            try:
                provider_pref = ProviderId(provider_pref)
            except ValueError:
                provider_pref = ProviderId.AUTO

        if provider_pref and provider_pref != ProviderId.AUTO:
            provider = self.registry.get(provider_pref)
            if provider and provider.enabled:
                model = request.model or resolve_default_model(provider_pref)
                return provider_pref, model

        # Auto mode
        task = self.classify(request.prompt, request.task_type)
        for pid in self.preferred_chain(task):
            provider = self.registry.get(pid)
            if provider and provider.enabled:
                return pid, resolve_default_model(pid)

        # Absolute last resort — any enabled provider
        enabled = self.registry.get_enabled()
        if enabled:
            p = enabled[0]
            return p.provider_id, resolve_default_model(p.provider_id)

        # Nothing configured — still return gemini defaults for mock mode
        return ProviderId.GEMINI, resolve_default_model(ProviderId.GEMINI)

    def fallback_chain(self, primary: ProviderId) -> List[ProviderId]:
        chain: List[ProviderId] = []
        for pid in FALLBACK_CHAIN:
            if pid != primary:
                provider = self.registry.get(pid)
                if provider and provider.enabled:
                    chain.append(pid)
        return chain
