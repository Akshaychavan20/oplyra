"""Knowledge Engine facade — collections, documents, search, stats, seeding."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func

from app import db
from app.models import (
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeEmbedding,
    KnowledgeSearchLog,
    KnowledgeVersion,
    KnowledgeTag,
    CollectionDocument,
)
from app.services.knowledge.pipeline import IngestPipeline
from app.services.knowledge.search import KnowledgeSearchService
from app.services.knowledge.types import SearchFilters
from app.services.knowledge.permissions import (
    get_user_org_id,
    can_read_document,
    can_write_document,
)


DEFAULT_COLLECTIONS = [
    ('workspace', 'Workspace Knowledge', 'Shared workspace documents'),
    ('brand', 'Brand Knowledge', 'Brand guidelines and voice'),
    ('personal', 'Personal Knowledge', 'Private notes and drafts'),
    ('global', 'Global Knowledge', 'Organization-wide playbooks'),
]


class KnowledgeService:
    def __init__(self):
        self.pipeline = IngestPipeline()
        self.search_service = KnowledgeSearchService()

    def ensure_default_collections(
        self,
        *,
        user_id: int,
        organization_id: Optional[int] = None,
    ) -> List[KnowledgeCollection]:
        org_id = organization_id or get_user_org_id(user_id)
        created = []
        for key, name, desc in DEFAULT_COLLECTIONS:
            existing = KnowledgeCollection.query.filter_by(
                organization_id=org_id,
                key=key,
                is_system=True,
            ).first()
            if existing:
                created.append(existing)
                continue
            row = KnowledgeCollection(
                organization_id=org_id,
                user_id=user_id,
                key=key,
                name=name,
                description=desc,
                collection_type=key if key in ('workspace', 'brand', 'personal', 'global') else 'workspace',
                is_system=True,
                is_active=True,
            )
            db.session.add(row)
            created.append(row)
        db.session.commit()
        return created

    def list_collections(self, user_id: int, organization_id: Optional[int] = None) -> List[Dict]:
        org_id = organization_id or get_user_org_id(user_id)
        self.ensure_default_collections(user_id=user_id, organization_id=org_id)
        rows = KnowledgeCollection.query.filter(
            KnowledgeCollection.is_active.is_(True),
            db.or_(
                KnowledgeCollection.organization_id == org_id,
                KnowledgeCollection.user_id == user_id,
                KnowledgeCollection.collection_type == 'global',
            ),
        ).order_by(KnowledgeCollection.name.asc()).all()
        out = []
        for c in rows:
            d = c.to_dict()
            d['document_count'] = CollectionDocument.query.filter_by(collection_id=c.id).count()
            out.append(d)
        return out

    def create_collection(
        self,
        *,
        user_id: int,
        name: str,
        collection_type: str = 'workspace',
        description: Optional[str] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ) -> KnowledgeCollection:
        org_id = organization_id or get_user_org_id(user_id)
        key = name.lower().replace(' ', '_')[:80]
        row = KnowledgeCollection(
            organization_id=org_id,
            user_id=user_id,
            project_id=project_id,
            campaign_id=campaign_id,
            key=key,
            name=name,
            description=description,
            collection_type=collection_type,
            is_system=False,
            is_active=True,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def list_documents(
        self,
        user_id: int,
        *,
        organization_id: Optional[int] = None,
        status: Optional[str] = 'active',
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        collection_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict]:
        org_id = organization_id or get_user_org_id(user_id)
        q = KnowledgeDocument.query.filter(KnowledgeDocument.status != 'deleted')
        if status:
            q = q.filter_by(status=status)
        if org_id is not None:
            q = q.filter(
                db.or_(
                    KnowledgeDocument.organization_id == org_id,
                    KnowledgeDocument.user_id == user_id,
                )
            )
        else:
            q = q.filter_by(user_id=user_id)
        if project_id:
            q = q.filter_by(project_id=project_id)
        if campaign_id:
            q = q.filter_by(campaign_id=campaign_id)
        if collection_id:
            q = q.join(CollectionDocument).filter(CollectionDocument.collection_id == collection_id)
        rows = q.order_by(KnowledgeDocument.updated_at.desc()).limit(min(limit, 200)).all()
        return [d.to_dict() for d in rows if can_read_document(user_id, d)]

    def get_document(self, document_id: int, user_id: int) -> Optional[KnowledgeDocument]:
        doc = KnowledgeDocument.query.get(document_id)
        if not doc or not can_read_document(user_id, doc):
            return None
        return doc

    def update_document(
        self,
        document: KnowledgeDocument,
        *,
        user_id: int,
        title: Optional[str] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> KnowledgeDocument:
        if not can_write_document(user_id, document):
            raise PermissionError('Not allowed to update this document')
        if title:
            document.title = title
        if status in ('active', 'archived', 'deleted'):
            document.status = status
        if visibility in ('private', 'shared'):
            document.visibility = visibility
        if tags is not None:
            KnowledgeTag.query.filter_by(document_id=document.id).delete()
            for tag in tags:
                tag = str(tag).strip()[:80]
                if tag:
                    db.session.add(KnowledgeTag(
                        organization_id=document.organization_id,
                        document_id=document.id,
                        tag=tag,
                    ))
        db.session.commit()
        if content is not None:
            document = self.pipeline.create_new_version(
                document, text=content, title=title, user_id=user_id,
            )
        return document

    def delete_document(self, document: KnowledgeDocument, user_id: int, hard: bool = False) -> None:
        if not can_write_document(user_id, document):
            raise PermissionError('Not allowed to delete this document')
        if hard:
            KnowledgeEmbedding.query.filter_by(document_id=document.id).delete()
            KnowledgeChunk.query.filter_by(document_id=document.id).delete()
            CollectionDocument.query.filter_by(document_id=document.id).delete()
            KnowledgeTag.query.filter_by(document_id=document.id).delete()
            KnowledgeVersion.query.filter_by(document_id=document.id).delete()
            db.session.delete(document)
        else:
            document.status = 'deleted'
        db.session.commit()

    def search(self, **kwargs):
        return self.search_service.search(**kwargs)

    def stats(self, user_id: int, organization_id: Optional[int] = None) -> Dict[str, Any]:
        org_id = organization_id or get_user_org_id(user_id)
        doc_q = KnowledgeDocument.query.filter(KnowledgeDocument.status != 'deleted')
        if org_id:
            doc_q = doc_q.filter(
                db.or_(
                    KnowledgeDocument.organization_id == org_id,
                    KnowledgeDocument.user_id == user_id,
                )
            )
        else:
            doc_q = doc_q.filter_by(user_id=user_id)

        doc_ids = [d.id for d in doc_q.all()]
        chunk_count = 0
        emb_count = 0
        storage = 0
        if doc_ids:
            chunk_count = KnowledgeChunk.query.filter(KnowledgeChunk.document_id.in_(doc_ids)).count()
            emb_count = KnowledgeEmbedding.query.filter(KnowledgeEmbedding.document_id.in_(doc_ids)).count()
            storage = db.session.query(func.coalesce(func.sum(KnowledgeDocument.file_size), 0)).filter(
                KnowledgeDocument.id.in_(doc_ids)
            ).scalar() or 0

        search_q = KnowledgeSearchLog.query
        if org_id:
            search_q = search_q.filter_by(organization_id=org_id)
        else:
            search_q = search_q.filter_by(user_id=user_id)
        search_count = search_q.count()
        recent = search_q.order_by(KnowledgeSearchLog.created_at.desc()).limit(100).all()
        avg_ms = int(sum(s.latency_ms or 0 for s in recent) / len(recent)) if recent else 0
        top_searches = (
            db.session.query(
                KnowledgeSearchLog.search_query,
                func.count(KnowledgeSearchLog.id),
            )
            .filter(KnowledgeSearchLog.user_id == user_id)
            .group_by(KnowledgeSearchLog.search_query)
            .order_by(func.count(KnowledgeSearchLog.id).desc())
            .limit(8)
            .all()
        )

        collections = self.list_collections(user_id, org_id)
        most_used = sorted(collections, key=lambda c: c.get('document_count', 0), reverse=True)[:5]

        return {
            'documents': len(doc_ids),
            'chunks': chunk_count,
            'embeddings': emb_count,
            'searches': search_count,
            'avg_retrieval_ms': avg_ms,
            'storage_bytes': int(storage),
            'collections': len(collections),
            'top_searches': [{'query': q, 'count': c} for q, c in top_searches],
            'most_used_collections': most_used,
        }
