"""Document ingest pipeline: extract → clean → chunk → embed → index → version."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import List, Optional

from flask import current_app
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEmbedding,
    KnowledgeVersion,
    CollectionDocument,
    KnowledgeTag,
)
from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.embeddings import get_embedding_provider
from app.services.knowledge.extractors import (
    clean_text,
    detect_doc_type,
    extract_from_bytes,
    extract_from_url,
)
from app.services.knowledge.vector_store import get_vector_store


class IngestPipeline:
    """Full indexing pipeline for the Knowledge Engine."""

    def __init__(self):
        self.embedder = get_embedding_provider()
        self.vector_store = get_vector_store()

    def _upload_dir(self) -> str:
        try:
            path = current_app.config.get('KNOWLEDGE_UPLOAD_FOLDER')
        except RuntimeError:
            path = os.path.join(os.getcwd(), 'uploads', 'knowledge')
        os.makedirs(path, exist_ok=True)
        return path

    def _chunk_params(self):
        try:
            size = int(current_app.config.get('KNOWLEDGE_CHUNK_SIZE') or 800)
            overlap = int(current_app.config.get('KNOWLEDGE_CHUNK_OVERLAP') or 120)
        except RuntimeError:
            size, overlap = 800, 120
        return size, overlap

    def ingest_upload(
        self,
        *,
        file_storage,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        title: Optional[str] = None,
        collection_ids: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        visibility: str = 'shared',
        doc_type_hint: Optional[str] = None,
    ) -> KnowledgeDocument:
        filename = secure_filename(file_storage.filename or 'document.txt')
        data = file_storage.read()
        doc_type = doc_type_hint or detect_doc_type(filename, file_storage.mimetype or '')
        checksum = hashlib.sha256(data).hexdigest()

        # Cloud object storage (local adapter in dev/test)
        from app.infra.storage import get_storage
        stored = get_storage().put(
            data,
            organization_id=organization_id,
            filename=filename,
            content_type=file_storage.mimetype,
            folder='knowledge',
            meta={'user_id': user_id, 'checksum': checksum},
        )
        storage_path = stored.url
        # Keep a local extractable copy for parsers when storage is remote URL
        abs_path = os.path.join(self._upload_dir(), f'{user_id}_{stored.key.replace("/", "_")}')
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb') as f:
            f.write(data)

        text = extract_from_bytes(data, doc_type, filename)
        return self._persist_and_index(
            title=title or filename,
            text=text,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            doc_type=doc_type,
            source_type='upload',
            source_uri=stored.key,
            storage_path=storage_path or abs_path,
            mime_type=file_storage.mimetype,
            file_size=len(data),
            checksum=checksum,
            collection_ids=collection_ids,
            tags=tags,
            visibility=visibility,
        )

    def ingest_text(
        self,
        *,
        title: str,
        text: str,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        doc_type: str = 'note',
        source_type: str = 'manual',
        collection_ids: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        visibility: str = 'shared',
    ) -> KnowledgeDocument:
        cleaned = clean_text(text)
        checksum = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()
        return self._persist_and_index(
            title=title,
            text=cleaned,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            doc_type=doc_type,
            source_type=source_type,
            source_uri=None,
            storage_path=None,
            mime_type='text/plain',
            file_size=len(cleaned.encode('utf-8')),
            checksum=checksum,
            collection_ids=collection_ids,
            tags=tags,
            visibility=visibility,
        )

    def ingest_url(
        self,
        *,
        url: str,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        title: Optional[str] = None,
        collection_ids: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        as_sitemap: bool = False,
    ) -> KnowledgeDocument:
        text, dtype = extract_from_url(url)
        if as_sitemap:
            dtype = 'sitemap'
        checksum = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return self._persist_and_index(
            title=title or url,
            text=text,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            doc_type=dtype,
            source_type='sitemap' if dtype == 'sitemap' else 'url',
            source_uri=url,
            storage_path=None,
            mime_type='text/html',
            file_size=len(text.encode('utf-8')),
            checksum=checksum,
            collection_ids=collection_ids,
            tags=tags,
            visibility='shared',
        )

    def reindex_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        version = (
            KnowledgeVersion.query.filter_by(
                document_id=document.id,
                version_number=document.current_version,
            ).first()
        )
        text = version.content_text if version else ''
        if not text and document.storage_path and os.path.exists(document.storage_path):
            with open(document.storage_path, 'rb') as f:
                data = f.read()
            text = extract_from_bytes(data, document.doc_type, document.title)

        # Clear old chunks/embeddings
        KnowledgeEmbedding.query.filter_by(document_id=document.id).delete()
        KnowledgeChunk.query.filter_by(document_id=document.id).delete()
        db.session.commit()
        self._index_text(document, text)
        return document

    def _persist_and_index(self, **kwargs) -> KnowledgeDocument:
        collection_ids = kwargs.pop('collection_ids', None) or []
        tags = kwargs.pop('tags', None) or []
        text = kwargs.pop('text')

        doc = KnowledgeDocument(
            organization_id=kwargs.get('organization_id'),
            user_id=kwargs.get('user_id'),
            project_id=kwargs.get('project_id'),
            campaign_id=kwargs.get('campaign_id'),
            title=kwargs['title'],
            doc_type=kwargs.get('doc_type') or 'txt',
            source_type=kwargs.get('source_type') or 'upload',
            source_uri=kwargs.get('source_uri'),
            storage_path=kwargs.get('storage_path'),
            mime_type=kwargs.get('mime_type'),
            file_size=kwargs.get('file_size') or 0,
            status='indexing',
            visibility=kwargs.get('visibility') or 'shared',
            current_version=1,
            checksum=kwargs.get('checksum'),
        )
        db.session.add(doc)
        db.session.flush()

        version = KnowledgeVersion(
            document_id=doc.id,
            version_number=1,
            title=doc.title,
            content_text=text,
            storage_path=doc.storage_path,
            checksum=doc.checksum,
            created_by=doc.user_id,
            change_note='Initial version',
        )
        db.session.add(version)

        for cid in collection_ids:
            db.session.add(CollectionDocument(collection_id=int(cid), document_id=doc.id))
        for tag in tags:
            tag = str(tag).strip()[:80]
            if tag:
                db.session.add(KnowledgeTag(
                    organization_id=doc.organization_id,
                    document_id=doc.id,
                    tag=tag,
                ))
        db.session.commit()

        try:
            self._index_text(doc, text)
        except Exception as exc:
            doc.status = 'failed'
            doc.error_message = str(exc)[:500]
            db.session.commit()
            raise
        return doc

    def _index_text(self, doc: KnowledgeDocument, text: str) -> None:
        size, overlap = self._chunk_params()
        chunks = chunk_text(text, chunk_size=size, overlap=overlap)
        if not chunks:
            chunks = [{'index': 0, 'content': text or doc.title, 'token_estimate': 1, 'meta': {}}]

        texts = [c['content'] for c in chunks]
        vectors = self.embedder.embed(texts)

        for spec, vector in zip(chunks, vectors):
            chunk = KnowledgeChunk(
                document_id=doc.id,
                version_number=doc.current_version,
                chunk_index=spec['index'],
                content=spec['content'],
                token_estimate=spec.get('token_estimate') or 0,
            )
            chunk.meta = spec.get('meta') or {}
            db.session.add(chunk)
            db.session.flush()
            self.vector_store.upsert(
                chunk_id=chunk.id,
                document_id=doc.id,
                organization_id=doc.organization_id,
                vector=vector,
                provider=self.embedder.provider_id,
                model=self.embedder.model,
            )

        doc.chunk_count = len(chunks)
        doc.embedding_count = len(chunks)
        doc.status = 'active'
        doc.indexed_at = datetime.utcnow()
        doc.error_message = None
        db.session.commit()

    def create_new_version(
        self,
        document: KnowledgeDocument,
        *,
        text: str,
        title: Optional[str] = None,
        user_id: Optional[int] = None,
        change_note: str = 'Updated content',
    ) -> KnowledgeDocument:
        document.current_version = (document.current_version or 1) + 1
        if title:
            document.title = title
        cleaned = clean_text(text)
        document.checksum = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()
        document.status = 'indexing'
        version = KnowledgeVersion(
            document_id=document.id,
            version_number=document.current_version,
            title=document.title,
            content_text=cleaned,
            checksum=document.checksum,
            created_by=user_id,
            change_note=change_note,
        )
        db.session.add(version)
        KnowledgeEmbedding.query.filter_by(document_id=document.id).delete()
        KnowledgeChunk.query.filter_by(document_id=document.id).delete()
        db.session.commit()
        self._index_text(document, cleaned)
        return document

    def restore_version(self, document: KnowledgeDocument, version_number: int, user_id: Optional[int] = None) -> KnowledgeDocument:
        version = KnowledgeVersion.query.filter_by(
            document_id=document.id,
            version_number=version_number,
        ).first()
        if not version or not version.content_text:
            raise ValueError('Version not found')
        return self.create_new_version(
            document,
            text=version.content_text,
            title=version.title,
            user_id=user_id,
            change_note=f'Restored from v{version_number}',
        )
