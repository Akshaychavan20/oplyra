"""Shared types for the multi-provider AI gateway."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderId(str, Enum):
    OPENAI = 'openai'
    GEMINI = 'gemini'
    ANTHROPIC = 'anthropic'
    DEEPSEEK = 'deepseek'
    # Future-ready slots (register adapters when enabled)
    GROK = 'grok'
    MISTRAL = 'mistral'
    COHERE = 'cohere'
    LLAMA = 'llama'
    PERPLEXITY = 'perplexity'
    OPENROUTER = 'openrouter'
    TOGETHER = 'together'
    OPENAI_COMPATIBLE = 'openai_compatible'
    AUTO = 'auto'


class TaskType(str, Enum):
    LONG_WRITING = 'long_writing'
    MARKETING_COPY = 'marketing_copy'
    SEO = 'seo'
    CODING = 'coding'
    IMAGE_ANALYSIS = 'image_analysis'
    PDF_ANALYSIS = 'pdf_analysis'
    FAST_CHEAP = 'fast_cheap'
    GENERAL_CHAT = 'general_chat'
    BLOG = 'blog'
    EMAIL = 'email'
    AD_COPY = 'ad_copy'
    SOCIAL = 'social'
    UNKNOWN = 'unknown'


@dataclass
class ModelSpec:
    provider: ProviderId
    model_id: str
    display_name: str
    supports_stream: bool = True
    supports_vision: bool = False
    supports_tools: bool = False
    supports_json: bool = True
    max_tokens_default: int = 4096
    input_cost_per_m: float = 0.0
    output_cost_per_m: float = 0.0
    enabled: bool = True
    experimental: bool = False


@dataclass
class AIRequest:
    prompt: str
    system_instruction: Optional[str] = None
    task_type: TaskType = TaskType.UNKNOWN
    provider: Optional[ProviderId] = None  # None / AUTO → router
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    json_mode: bool = False
    timeout: Optional[float] = None
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    workspace_id: Optional[int] = None
    campaign_id: Optional[int] = None
    skip_cache: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional multimodal payloads (provider adapters may ignore if unsupported)
    images: List[Any] = field(default_factory=list)
    documents: List[Any] = field(default_factory=list)


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    cost: float = 0.0
    cached: bool = False
    fallback_used: bool = False
    retry_count: int = 0
    finish_reason: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    @property
    def tokens(self) -> int:
        """Backward-compatible alias used by legacy callers."""
        return self.total_tokens or (self.input_tokens + self.output_tokens)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
