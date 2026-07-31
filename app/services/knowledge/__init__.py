"""
Enterprise Knowledge Engine + RAG Platform.

Sits above Agent Manager. Never calls AI providers for generation directly for RAG answers —
retrieval only; agents still go through Agent Manager → AI Gateway.
"""
from app.services.knowledge.service import KnowledgeService

__all__ = ['KnowledgeService']
