"""RAG context builder — injects retrieved chunks into agent prompts (never raw files)."""
from __future__ import annotations

from typing import List, Optional

from flask import current_app

from app.services.knowledge.search import KnowledgeSearchService
from app.services.knowledge.types import SearchFilters, SearchHit


class KnowledgeRAG:
    """Retrieval Augmented Generation helper for Agent Manager context."""

    def __init__(self, search: Optional[KnowledgeSearchService] = None):
        self.search = search or KnowledgeSearchService()

    def _enabled(self) -> bool:
        try:
            return bool(current_app.config.get('KNOWLEDGE_RAG_ENABLED', True))
        except RuntimeError:
            return True

    def _top_k(self) -> int:
        try:
            return int(current_app.config.get('KNOWLEDGE_TOP_K') or 6)
        except RuntimeError:
            return 6

    def retrieve(
        self,
        query: str,
        *,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        collection_ids: Optional[List[int]] = None,
        top_k: Optional[int] = None,
    ) -> List[SearchHit]:
        if not self._enabled() or not query:
            return []
        filters = SearchFilters(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            campaign_id=campaign_id,
            collection_ids=collection_ids,
            status='active',
        )
        return self.search.search(
            query,
            top_k=top_k or self._top_k(),
            search_type='hybrid',
            filters=filters,
            user_id=user_id,
            organization_id=organization_id,
            log=True,
        )

    def format_context(self, hits: List[SearchHit], *, max_chars: int = 6000) -> str:
        if not hits:
            return ''
        parts = ['## Retrieved Knowledge (use as ground truth; cite document titles when relevant)']
        used = 0
        for i, hit in enumerate(hits, 1):
            block = (
                f'\n### Source {i}: {hit.document_title or "Document"} '
                f'(score={hit.score:.2f})\n{hit.content.strip()}\n'
            )
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
        return '\n'.join(parts).strip()

    def retrieve_context_text(
        self,
        query: str,
        *,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
    ) -> str:
        hits = self.retrieve(
            query,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
        )
        return self.format_context(hits)


def inject_rag_into_context(
    ctx: dict,
    *,
    user_id: int,
    goal: str,
    project_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> dict:
    """
    Additive hook for AgentMemoryService — does not rewrite the Agent Framework.
    Appends retrieved knowledge into ctx['extras'].
    """
    try:
        rag = KnowledgeRAG()
        text = rag.retrieve_context_text(
            goal,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
        )
        if text:
            existing = (ctx.get('extras') or '').strip()
            ctx['extras'] = f'{existing}\n\n{text}'.strip() if existing else text
            ctx['knowledge_hits'] = True
    except Exception:
        # Knowledge engine optional — never break agent runs
        pass
    return ctx
