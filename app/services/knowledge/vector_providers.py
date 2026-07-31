"""Production vector DB providers — Qdrant, Pinecone, Weaviate, pgvector.

Hydrates chunk content from SQL after remote ANN search.
Falls back to LocalVectorStore when credentials are missing (non-production).
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import requests

from app import db
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding
from app.services.knowledge.types import SearchFilters, SearchHit
from app.services.knowledge.vector_store import LocalVectorStore, VectorStore

logger = logging.getLogger(__name__)


def _hydrate_hits(scored_ids: List[tuple]) -> List[SearchHit]:
    """scored_ids: list of (chunk_id, score)."""
    hits: List[SearchHit] = []
    for chunk_id, score in scored_ids:
        chunk = KnowledgeChunk.query.get(chunk_id)
        if not chunk:
            continue
        doc = KnowledgeDocument.query.get(chunk.document_id)
        if not doc or doc.status != 'active':
            continue
        hits.append(SearchHit(
            chunk_id=chunk.id,
            document_id=doc.id,
            content=chunk.content,
            score=float(score),
            document_title=doc.title,
            doc_type=doc.doc_type,
            meta=chunk.meta,
        ))
    return hits


def _mirror_local(**kwargs):
    """Keep SQL embedding row for hydration / local fallback."""
    LocalVectorStore().upsert(**kwargs)


def _is_production() -> bool:
    try:
        from flask import current_app
        return bool(current_app.config.get('ENV') == 'production'
                    or (not current_app.debug and not current_app.testing
                        and current_app.config.get('USE_ALEMBIC_ONLY')))
    except RuntimeError:
        return os.environ.get('FLASK_ENV') == 'production'


class QdrantVectorStore(VectorStore):
    provider_id = 'qdrant'

    def __init__(self):
        self.url = (os.environ.get('QDRANT_URL') or self._cfg('QDRANT_URL', '')).rstrip('/')
        self.api_key = os.environ.get('QDRANT_API_KEY') or self._cfg('QDRANT_API_KEY', '')
        self.collection = os.environ.get('QDRANT_COLLECTION') or self._cfg('QDRANT_COLLECTION', 'oplyra_chunks')
        self._local = LocalVectorStore()

    def _cfg(self, key, default=''):
        try:
            from flask import current_app
            return current_app.config.get(key, default) or default
        except RuntimeError:
            return default

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.api_key:
            h['api-key'] = self.api_key
        return h

    def _configured(self) -> bool:
        return bool(self.url)

    def upsert(self, *, chunk_id, document_id, organization_id, vector, provider, model):
        _mirror_local(
            chunk_id=chunk_id, document_id=document_id, organization_id=organization_id,
            vector=vector, provider=provider, model=model,
        )
        if not self._configured():
            if _is_production():
                raise RuntimeError('QDRANT_URL is required when KNOWLEDGE_VECTOR_PROVIDER=qdrant')
            return
        point = {
            'id': chunk_id,
            'vector': vector,
            'payload': {
                'chunk_id': chunk_id,
                'document_id': document_id,
                'organization_id': organization_id,
            },
        }
        try:
            requests.put(
                f'{self.url}/collections/{self.collection}/points',
                json={'points': [point]},
                headers=self._headers(),
                timeout=15,
            ).raise_for_status()
        except Exception as exc:
            logger.error('Qdrant upsert failed: %s', type(exc).__name__)
            if _is_production():
                raise

    def delete_document(self, document_id: int) -> None:
        chunks = KnowledgeChunk.query.filter_by(document_id=document_id).all()
        ids = [c.id for c in chunks]
        self._local.delete_document(document_id)
        if not self._configured() or not ids:
            return
        try:
            requests.post(
                f'{self.url}/collections/{self.collection}/points/delete',
                json={'points': ids},
                headers=self._headers(),
                timeout=15,
            )
        except Exception as exc:
            logger.warning('Qdrant delete failed: %s', type(exc).__name__)

    def search(self, query_vector, *, top_k=6, filters=None):
        filters = filters or SearchFilters()
        if not self._configured():
            return self._local.search(query_vector, top_k=top_k, filters=filters)
        must = []
        if filters.organization_id is not None:
            must.append({'key': 'organization_id', 'match': {'value': filters.organization_id}})
        body = {
            'vector': query_vector,
            'limit': top_k,
            'with_payload': True,
        }
        if must:
            body['filter'] = {'must': must}
        try:
            res = requests.post(
                f'{self.url}/collections/{self.collection}/points/search',
                json=body,
                headers=self._headers(),
                timeout=15,
            )
            res.raise_for_status()
            points = res.json().get('result') or []
            scored = []
            for p in points:
                payload = p.get('payload') or {}
                cid = payload.get('chunk_id') or p.get('id')
                scored.append((int(cid), float(p.get('score') or 0)))
            return _hydrate_hits(scored)
        except Exception as exc:
            logger.error('Qdrant search failed, falling back local: %s', type(exc).__name__)
            if _is_production():
                raise
            return self._local.search(query_vector, top_k=top_k, filters=filters)


class PineconeVectorStore(VectorStore):
    provider_id = 'pinecone'

    def __init__(self):
        self.api_key = os.environ.get('PINECONE_API_KEY') or self._cfg('PINECONE_API_KEY', '')
        self.host = (os.environ.get('PINECONE_HOST') or self._cfg('PINECONE_HOST', '')).rstrip('/')
        self._local = LocalVectorStore()

    def _cfg(self, key, default=''):
        try:
            from flask import current_app
            return current_app.config.get(key, default) or default
        except RuntimeError:
            return default

    def _configured(self):
        return bool(self.api_key and self.host)

    def _headers(self):
        return {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

    def upsert(self, *, chunk_id, document_id, organization_id, vector, provider, model):
        _mirror_local(
            chunk_id=chunk_id, document_id=document_id, organization_id=organization_id,
            vector=vector, provider=provider, model=model,
        )
        if not self._configured():
            if _is_production():
                raise RuntimeError('PINECONE_API_KEY and PINECONE_HOST required')
            return
        body = {
            'vectors': [{
                'id': str(chunk_id),
                'values': vector,
                'metadata': {
                    'chunk_id': chunk_id,
                    'document_id': document_id,
                    'organization_id': organization_id or 0,
                },
            }]
        }
        try:
            requests.post(f'{self.host}/vectors/upsert', json=body, headers=self._headers(), timeout=15).raise_for_status()
        except Exception as exc:
            logger.error('Pinecone upsert failed: %s', type(exc).__name__)
            if _is_production():
                raise

    def delete_document(self, document_id: int) -> None:
        chunks = KnowledgeChunk.query.filter_by(document_id=document_id).all()
        ids = [str(c.id) for c in chunks]
        self._local.delete_document(document_id)
        if not self._configured() or not ids:
            return
        try:
            requests.post(
                f'{self.host}/vectors/delete',
                json={'ids': ids},
                headers=self._headers(),
                timeout=15,
            )
        except Exception as exc:
            logger.warning('Pinecone delete failed: %s', type(exc).__name__)

    def search(self, query_vector, *, top_k=6, filters=None):
        filters = filters or SearchFilters()
        if not self._configured():
            return self._local.search(query_vector, top_k=top_k, filters=filters)
        body = {'vector': query_vector, 'topK': top_k, 'includeMetadata': True}
        if filters.organization_id is not None:
            body['filter'] = {'organization_id': {'$eq': filters.organization_id}}
        try:
            res = requests.post(f'{self.host}/query', json=body, headers=self._headers(), timeout=15)
            res.raise_for_status()
            matches = res.json().get('matches') or []
            scored = []
            for m in matches:
                meta = m.get('metadata') or {}
                cid = meta.get('chunk_id') or m.get('id')
                scored.append((int(cid), float(m.get('score') or 0)))
            return _hydrate_hits(scored)
        except Exception as exc:
            logger.error('Pinecone search failed: %s', type(exc).__name__)
            if _is_production():
                raise
            return self._local.search(query_vector, top_k=top_k, filters=filters)


class WeaviateVectorStore(VectorStore):
    provider_id = 'weaviate'

    def __init__(self):
        self.url = (os.environ.get('WEAVIATE_URL') or self._cfg('WEAVIATE_URL', '')).rstrip('/')
        self.api_key = os.environ.get('WEAVIATE_API_KEY') or self._cfg('WEAVIATE_API_KEY', '')
        self.class_name = os.environ.get('WEAVIATE_CLASS') or self._cfg('WEAVIATE_CLASS', 'OplyraChunk')
        self._local = LocalVectorStore()

    def _cfg(self, key, default=''):
        try:
            from flask import current_app
            return current_app.config.get(key, default) or default
        except RuntimeError:
            return default

    def _configured(self):
        return bool(self.url)

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.api_key:
            h['Authorization'] = f'Bearer {self.api_key}'
        return h

    def upsert(self, *, chunk_id, document_id, organization_id, vector, provider, model):
        _mirror_local(
            chunk_id=chunk_id, document_id=document_id, organization_id=organization_id,
            vector=vector, provider=provider, model=model,
        )
        if not self._configured():
            if _is_production():
                raise RuntimeError('WEAVIATE_URL required')
            return
        body = {
            'class': self.class_name,
            'id': str(uuid_from_int(chunk_id)),
            'vector': vector,
            'properties': {
                'chunk_id': chunk_id,
                'document_id': document_id,
                'organization_id': organization_id or 0,
            },
        }
        try:
            requests.post(f'{self.url}/v1/objects', json=body, headers=self._headers(), timeout=15).raise_for_status()
        except Exception as exc:
            logger.error('Weaviate upsert failed: %s', type(exc).__name__)
            if _is_production():
                raise

    def delete_document(self, document_id: int) -> None:
        self._local.delete_document(document_id)
        # Best-effort: where filter delete not always available; leave orphan vectors TTL'd externally

    def search(self, query_vector, *, top_k=6, filters=None):
        filters = filters or SearchFilters()
        if not self._configured():
            return self._local.search(query_vector, top_k=top_k, filters=filters)
        graphql = {
            'query': f"""
            {{
              Get {{
                {self.class_name}(
                  nearVector: {{vector: {query_vector}}}
                  limit: {top_k}
                ) {{
                  chunk_id
                  document_id
                  _additional {{ distance }}
                }}
              }}
            }}
            """
        }
        try:
            res = requests.post(f'{self.url}/v1/graphql', json=graphql, headers=self._headers(), timeout=15)
            res.raise_for_status()
            items = (((res.json().get('data') or {}).get('Get') or {}).get(self.class_name)) or []
            scored = []
            for item in items:
                dist = ((item.get('_additional') or {}).get('distance')) or 0
                score = 1.0 / (1.0 + float(dist))
                scored.append((int(item['chunk_id']), score))
            return _hydrate_hits(scored)
        except Exception as exc:
            logger.error('Weaviate search failed: %s', type(exc).__name__)
            if _is_production():
                raise
            return self._local.search(query_vector, top_k=top_k, filters=filters)


def uuid_from_int(n: int) -> str:
    """Deterministic UUID-ish hex for Weaviate object ids."""
    return f'{n:032x}'


class PgVectorStore(VectorStore):
    """PostgreSQL pgvector — uses <=> when extension available, else local."""

    provider_id = 'pgvector'

    def __init__(self):
        self._local = LocalVectorStore()

    def upsert(self, **kwargs):
        return self._local.upsert(**kwargs)

    def delete_document(self, document_id: int) -> None:
        return self._local.delete_document(document_id)

    def search(self, query_vector, *, top_k=6, filters=None):
        filters = filters or SearchFilters()
        try:
            from flask import current_app
            uri = current_app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        except RuntimeError:
            uri = ''
        if not uri.startswith('postgresql'):
            return self._local.search(query_vector, top_k=top_k, filters=filters)

        # Attempt native pgvector query; fall back on any error
        try:
            from sqlalchemy import text
            vec_literal = '[' + ','.join(str(float(x)) for x in query_vector) + ']'
            sql = text("""
                SELECT ke.chunk_id, 1 - (ke.embedding <=> CAST(:vec AS vector)) AS score
                FROM knowledge_embeddings ke
                JOIN knowledge_documents kd ON kd.id = ke.document_id
                WHERE kd.status = 'active'
                  AND (:org_id IS NULL OR ke.organization_id = :org_id OR ke.organization_id IS NULL)
                ORDER BY ke.embedding <=> CAST(:vec AS vector)
                LIMIT :top_k
            """)
            rows = db.session.execute(sql, {
                'vec': vec_literal,
                'org_id': filters.organization_id,
                'top_k': top_k,
            }).fetchall()
            return _hydrate_hits([(int(r[0]), float(r[1] or 0)) for r in rows])
        except Exception as exc:
            logger.info('pgvector path unavailable (%s); using local cosine', type(exc).__name__)
            return self._local.search(query_vector, top_k=top_k, filters=filters)
