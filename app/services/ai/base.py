"""Provider abstraction — every LLM vendor implements this interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator, Iterable, List, Optional

from app.services.ai.types import AIRequest, AIResponse, ModelSpec, ProviderId


class BaseProvider(ABC):
    """
    Pluggable AI provider contract.

    Application / route code must never call providers directly.
    Only AIGateway + ProviderRegistry may.
    """

    provider_id: ProviderId
    display_name: str = 'Provider'

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self.is_configured())

    def set_enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def is_configured(self) -> bool:
        """True when an API key (or mock key) is present."""
        return bool(self.api_key)

    def is_mock_key(self) -> bool:
        return not self.api_key or str(self.api_key).startswith('your_')

    @abstractmethod
    def list_models(self) -> List[ModelSpec]:
        raise NotImplementedError

    @abstractmethod
    def generate_text(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    def chat(self, request: AIRequest) -> AIResponse:
        return self.generate_text(request)

    def stream(self, request: AIRequest) -> Generator[str, None, None]:
        """Default: non-streaming fallback yielding full text once."""
        response = self.generate_text(request)
        yield response.text

    def generate_image(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError(f'{self.provider_id.value} does not support generate_image')

    def analyze_image(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError(f'{self.provider_id.value} does not support analyze_image')

    def analyze_pdf(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError(f'{self.provider_id.value} does not support analyze_pdf')

    def vision(self, request: AIRequest) -> AIResponse:
        return self.analyze_image(request)

    def embeddings(self, texts: Iterable[str], model: Optional[str] = None) -> List[List[float]]:
        raise NotImplementedError(f'{self.provider_id.value} does not support embeddings')

    def tool_calling(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError(f'{self.provider_id.value} does not support tool_calling')

    def health_check(self) -> bool:
        return self.is_configured()
