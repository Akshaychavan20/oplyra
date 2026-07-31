"""Enterprise infrastructure layer — storage, queues, logging, health, rate limits.

Does not replace AI Gateway, Agents, Knowledge Engine, or MCP business logic.
"""
from app.infra.redis_client import get_redis
from app.infra.storage import get_storage
from app.infra.logging_setup import configure_structured_logging, get_request_id

__all__ = [
    'get_redis',
    'get_storage',
    'configure_structured_logging',
    'get_request_id',
]
