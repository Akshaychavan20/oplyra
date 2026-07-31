"""
Oplyra Multi-Provider AI package.

Application code must only talk to AIGateway (app.services.ai_gateway).
Providers are pluggable adapters behind ProviderRegistry + TaskRouter.
"""
from app.services.ai.types import (
    AIRequest,
    AIResponse,
    TaskType,
    ProviderId,
    ModelSpec,
)
from app.services.ai.registry import ProviderRegistry

__all__ = [
    'AIRequest',
    'AIResponse',
    'TaskType',
    'ProviderId',
    'ModelSpec',
    'ProviderRegistry',
]
