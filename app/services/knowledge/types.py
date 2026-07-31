"""Shared types for the Knowledge Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SUPPORTED_DOC_TYPES = frozenset({
    'pdf', 'docx', 'txt', 'csv', 'xlsx', 'markdown', 'html', 'json',
    'url', 'sitemap', 'note', 'brand', 'marketing', 'research',
    'case_study', 'playbook', 'xml',
})

COLLECTION_TYPES = frozenset({
    'workspace', 'client', 'campaign', 'brand', 'personal', 'global',
})

DOC_STATUS = frozenset({'active', 'archived', 'deleted', 'indexing', 'failed'})


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    content: str
    score: float
    document_title: str = ''
    doc_type: str = ''
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'content': self.content,
            'score': round(self.score, 4),
            'document_title': self.document_title,
            'doc_type': self.doc_type,
            'meta': self.meta,
        }


@dataclass
class SearchFilters:
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    project_id: Optional[int] = None
    campaign_id: Optional[int] = None
    collection_ids: Optional[List[int]] = None
    doc_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None
    status: str = 'active'
