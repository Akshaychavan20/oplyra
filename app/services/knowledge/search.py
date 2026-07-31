"""Semantic, keyword, and hybrid search for the Knowledge Engine."""
from __future__ import annotations

import re
import time
from typing import List, Optional

from app import db
from app.models import KnowledgeSearchLog, KnowledgeChunk, KnowledgeDocument
from app.services.knowledge.embeddings import get_embedding_provider
from app.services.knowledge.types import SearchFilters, SearchHit
from app.services.knowledge.vector_store import get_vector_store


class KnowledgeSearchService:
    def __init__(self):
        self.embedder = get_embedding_provider()
        self.vector_store = get_vector_store()

    def search(
        self,
        query: str,
        *,
        top_k: int = 6,
        search_type: str = 'hybrid',
        filters: Optional[SearchFilters] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        log: bool = True,
    ) -> List[SearchHit]:
        query = (query or '').strip()
        if not query:
            return []
        filters = filters or SearchFilters()
        if organization_id is not None:
            filters.organization_id = organization_id
        if user_id is not None:
            filters.user_id = user_id

        started = time.perf_counter()
        search_type = (search_type or 'hybrid').lower()

        if search_type == 'keyword':
            hits = self._keyword_search(query, top_k=top_k, filters=filters)
        elif search_type == 'semantic':
            hits = self._semantic_search(query, top_k=top_k, filters=filters)
        else:
            hits = self._hybrid_search(query, top_k=top_k, filters=filters)

        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            from app.infra.metrics import incr, observe
            incr('knowledge.searches')
            observe('knowledge.search_latency', latency_ms)
        except Exception:
            pass
        if log:
            entry = KnowledgeSearchLog(
                organization_id=filters.organization_id,
                user_id=user_id,
                search_query=query[:500],
                search_type=search_type,
                top_k=top_k,
                result_count=len(hits),
                latency_ms=latency_ms,
                project_id=filters.project_id,
                campaign_id=filters.campaign_id,
            )
            if filters.collection_ids:
                import json
                entry.collection_ids_json = json.dumps(filters.collection_ids)
            db.session.add(entry)
            db.session.commit()
        return hits

    def _semantic_search(self, query: str, *, top_k: int, filters: SearchFilters) -> List[SearchHit]:
        qvec = self.embedder.embed_one(query)
        return self.vector_store.search(qvec, top_k=top_k, filters=filters)

    def _keyword_search(self, query: str, *, top_k: int, filters: SearchFilters) -> List[SearchHit]:
        tokens = [t for t in re.findall(r'\w+', query.lower()) if len(t) > 2]
        q = (
            db.session.query(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .filter(KnowledgeDocument.status == (filters.status or 'active'))
        )
        if filters.organization_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.organization_id == filters.organization_id,
                    KnowledgeDocument.organization_id.is_(None),
                )
            )
        if filters.project_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.project_id == filters.project_id,
                    KnowledgeDocument.project_id.is_(None),
                )
            )
        if filters.campaign_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.campaign_id == filters.campaign_id,
                    KnowledgeDocument.campaign_id.is_(None),
                )
            )
        if filters.user_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.visibility == 'shared',
                    KnowledgeDocument.user_id == filters.user_id,
                )
            )

        rows = q.limit(500).all()
        scored = []
        for chunk, doc in rows:
            content_l = (chunk.content or '').lower()
            title_l = (doc.title or '').lower()
            score = 0.0
            for tok in tokens:
                score += content_l.count(tok) * 1.0
                score += title_l.count(tok) * 2.0
            if query.lower() in content_l:
                score += 5.0
            if score > 0:
                scored.append(SearchHit(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    content=chunk.content,
                    score=score,
                    document_title=doc.title,
                    doc_type=doc.doc_type,
                    meta=chunk.meta,
                ))
        scored.sort(key=lambda h: h.score, reverse=True)
        # Normalize keyword scores to 0-1 range for hybrid merge
        if scored:
            max_s = scored[0].score or 1.0
            for h in scored:
                h.score = h.score / max_s
        return scored[:top_k]

    def _hybrid_search(self, query: str, *, top_k: int, filters: SearchFilters) -> List[SearchHit]:
        semantic = self._semantic_search(query, top_k=top_k * 3, filters=filters)
        keyword = self._keyword_search(query, top_k=top_k * 3, filters=filters)
        by_chunk = {}
        for h in semantic:
            by_chunk[h.chunk_id] = SearchHit(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                content=h.content,
                score=h.score * 0.7,
                document_title=h.document_title,
                doc_type=h.doc_type,
                meta=h.meta,
            )
        for h in keyword:
            if h.chunk_id in by_chunk:
                by_chunk[h.chunk_id].score += h.score * 0.3
            else:
                by_chunk[h.chunk_id] = SearchHit(
                    chunk_id=h.chunk_id,
                    document_id=h.document_id,
                    content=h.content,
                    score=h.score * 0.3,
                    document_title=h.document_title,
                    doc_type=h.doc_type,
                    meta=h.meta,
                )
        merged = sorted(by_chunk.values(), key=lambda x: x.score, reverse=True)
        return merged[:top_k]
