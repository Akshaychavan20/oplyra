"""Vector database provider abstraction — never hardcode a store."""
from __future__ import annotations

import logging
import math
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence, Tuple

from flask import current_app

from app import db
from app.models import KnowledgeEmbedding, KnowledgeChunk, KnowledgeDocument, CollectionDocument
from app.services.knowledge.types import SearchFilters, SearchHit

logger = logging.getLogger(__name__)

# Safety cap for local full-scan (dev/test only). Production must use ANN providers.
LOCAL_MAX_SCAN = 5000


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class VectorStore(ABC):
    provider_id: str = 'base'

    @abstractmethod
    def upsert(
        self,
        *,
        chunk_id: int,
        document_id: int,
        organization_id: Optional[int],
        vector: List[float],
        provider: str,
        model: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        *,
        top_k: int = 6,
        filters: Optional[SearchFilters] = None,
    ) -> List[SearchHit]:
        raise NotImplementedError

    def healthcheck(self) -> bool:
        return True


class LocalVectorStore(VectorStore):
    """SQL-backed cosine similarity — development/testing only (capped scan)."""

    provider_id = 'local'

    def upsert(
        self,
        *,
        chunk_id: int,
        document_id: int,
        organization_id: Optional[int],
        vector: List[float],
        provider: str,
        model: str,
    ) -> None:
        row = KnowledgeEmbedding.query.filter_by(chunk_id=chunk_id).first()
        if not row:
            row = KnowledgeEmbedding(chunk_id=chunk_id, document_id=document_id)
            db.session.add(row)
        row.organization_id = organization_id
        row.provider = provider
        row.model = model
        row.dims = len(vector)
        row.vector = vector
        db.session.commit()

    def delete_document(self, document_id: int) -> None:
        KnowledgeEmbedding.query.filter_by(document_id=document_id).delete()
        db.session.commit()

    def search(
        self,
        query_vector: List[float],
        *,
        top_k: int = 6,
        filters: Optional[SearchFilters] = None,
    ) -> List[SearchHit]:
        filters = filters or SearchFilters()
        q = (
            db.session.query(KnowledgeEmbedding, KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeChunk, KnowledgeChunk.id == KnowledgeEmbedding.chunk_id)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeEmbedding.document_id)
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
        if filters.visibility:
            q = q.filter(KnowledgeDocument.visibility == filters.visibility)
        if filters.doc_types:
            q = q.filter(KnowledgeDocument.doc_type.in_(filters.doc_types))
        if filters.collection_ids:
            q = q.join(
                CollectionDocument,
                CollectionDocument.document_id == KnowledgeDocument.id,
            ).filter(CollectionDocument.collection_id.in_(filters.collection_ids))
        if filters.user_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.visibility == 'shared',
                    KnowledgeDocument.user_id == filters.user_id,
                )
            )

        # Cap scan — prevents unbounded memory growth; prefer ANN providers in prod
        try:
            max_scan = int(current_app.config.get('LOCAL_VECTOR_MAX_SCAN') or LOCAL_MAX_SCAN)
        except RuntimeError:
            max_scan = LOCAL_MAX_SCAN

        rows = q.order_by(KnowledgeEmbedding.id.desc()).limit(max_scan).all()
        scored: List[Tuple[float, KnowledgeEmbedding, KnowledgeChunk, KnowledgeDocument]] = []
        for emb, chunk, doc in rows:
            score = cosine_similarity(query_vector, emb.vector)
            scored.append((score, emb, chunk, doc))
        scored.sort(key=lambda t: t[0], reverse=True)

        hits: List[SearchHit] = []
        for score, emb, chunk, doc in scored[:top_k]:
            hits.append(SearchHit(
                chunk_id=chunk.id,
                document_id=doc.id,
                content=chunk.content,
                score=score,
                document_title=doc.title,
                doc_type=doc.doc_type,
                meta=chunk.meta,
            ))
        return hits


def get_vector_store(name: Optional[str] = None) -> VectorStore:
    try:
        provider = (name or current_app.config.get('KNOWLEDGE_VECTOR_PROVIDER') or 'local').lower()
    except RuntimeError:
        provider = (name or os.environ.get('KNOWLEDGE_VECTOR_PROVIDER') or 'local').lower()

    if provider == 'local':
        return LocalVectorStore()

    # Lazy import production providers
    from app.services.knowledge.vector_providers import (
        QdrantVectorStore,
        PineconeVectorStore,
        WeaviateVectorStore,
        PgVectorStore,
    )
    registry = {
        'qdrant': QdrantVectorStore,
        'pinecone': PineconeVectorStore,
        'weaviate': WeaviateVectorStore,
        'pgvector': PgVectorStore,
        # Aliases / legacy names map to real adapters
        'chroma': LocalVectorStore,
        'milvus': QdrantVectorStore,
    }
    cls = registry.get(provider)
    if not cls:
        logger.warning('Unknown vector provider %s; using local', provider)
        return LocalVectorStore()
    return cls()
