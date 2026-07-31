"""
/api/knowledge/* — Enterprise Knowledge Engine HTTP surface.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.models import KnowledgeVersion, KnowledgeTag, CollectionDocument
from app.services.knowledge.service import KnowledgeService
from app.services.knowledge.permissions import get_user_org_id
from app.services.knowledge.types import SearchFilters
from app.services.knowledge.pipeline import IngestPipeline

knowledge_bp = Blueprint('knowledge', __name__)


def _svc() -> KnowledgeService:
    return KnowledgeService()


def _org_id():
    return get_user_org_id(current_user.id)


@knowledge_bp.route('', methods=['GET'])
@knowledge_bp.route('/', methods=['GET'])
@login_required
def knowledge_home():
    """GET /api/knowledge — dashboard summary + recent documents."""
    svc = _svc()
    org_id = _org_id()
    return jsonify({
        'success': True,
        'stats': svc.stats(current_user.id, org_id),
        'documents': svc.list_documents(current_user.id, organization_id=org_id, limit=12),
        'collections': svc.list_collections(current_user.id, org_id),
    })


@knowledge_bp.route('/upload', methods=['POST'])
@login_required
def upload_document():
    """POST /api/knowledge/upload — multipart file or JSON text/url."""
    from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
    try:
        enforce_rate_limit('upload', identity=f'user:{current_user.id}', organization_id=_org_id())
    except RateLimitExceeded as exc:
        return jsonify({'success': False, 'error': str(exc), 'error_code': 'RATE_LIMITED'}), 429
    org_id = _org_id()
    pipeline = IngestPipeline()

    collection_ids = request.form.getlist('collection_ids') or []
    data = request.get_json(silent=True) or {}
    if not collection_ids:
        collection_ids = data.get('collection_ids') or []
    collection_ids = [int(c) for c in collection_ids if str(c).isdigit()]

    tags_raw = request.form.get('tags') or ''
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    if data.get('tags') and isinstance(data['tags'], list):
        tags = data['tags']

    # JSON body: manual note or URL
    if data.get('url') or data.get('text') or data.get('content'):
        if data.get('url'):
            try:
                doc = pipeline.ingest_url(
                    url=data['url'],
                    user_id=current_user.id,
                    organization_id=org_id,
                    project_id=data.get('project_id'),
                    campaign_id=data.get('campaign_id'),
                    title=data.get('title'),
                    collection_ids=collection_ids,
                    tags=tags,
                    as_sitemap=bool(data.get('sitemap')),
                )
            except Exception as exc:
                return jsonify({'success': False, 'error': str(exc)}), 400
            return jsonify({'success': True, 'document': doc.to_dict()}), 201

        title = (data.get('title') or 'Untitled note').strip()
        text = (data.get('text') or data.get('content') or '').strip()
        if not text:
            return jsonify({'success': False, 'error': 'text or url or file is required'}), 400
        doc = pipeline.ingest_text(
            title=title,
            text=text,
            user_id=current_user.id,
            organization_id=org_id,
            project_id=data.get('project_id'),
            campaign_id=data.get('campaign_id'),
            doc_type=data.get('doc_type') or 'note',
            source_type='manual',
            collection_ids=collection_ids,
            tags=tags,
            visibility=data.get('visibility') or 'shared',
        )
        return jsonify({'success': True, 'document': doc.to_dict()}), 201

    f = request.files.get('file')
    if not f:
        return jsonify({'success': False, 'error': 'file is required'}), 400
    try:
        doc = pipeline.ingest_upload(
            file_storage=f,
            user_id=current_user.id,
            organization_id=org_id,
            project_id=request.form.get('project_id', type=int),
            campaign_id=request.form.get('campaign_id', type=int),
            title=request.form.get('title'),
            collection_ids=collection_ids,
            tags=tags,
            visibility=request.form.get('visibility') or 'shared',
            doc_type_hint=request.form.get('doc_type'),
        )
    except Exception as exc:
        return jsonify({'success': False, 'error': f'Ingest failed: {exc}'}), 400
    return jsonify({'success': True, 'document': doc.to_dict()}), 201


@knowledge_bp.route('/search', methods=['POST'])
@login_required
def search_knowledge():
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or data.get('q') or '').strip()
    if not query:
        return jsonify({'success': False, 'error': 'query is required'}), 400

    filters = SearchFilters(
        organization_id=_org_id(),
        user_id=current_user.id,
        project_id=data.get('project_id'),
        campaign_id=data.get('campaign_id'),
        collection_ids=data.get('collection_ids'),
        doc_types=data.get('doc_types'),
        tags=data.get('tags'),
        status=data.get('status') or 'active',
    )
    hits = _svc().search(
        query=query,
        top_k=int(data.get('top_k') or 6),
        search_type=data.get('search_type') or 'hybrid',
        filters=filters,
        user_id=current_user.id,
        organization_id=_org_id(),
    )
    return jsonify({
        'success': True,
        'results': [h.to_dict() for h in hits],
        'count': len(hits),
    })


@knowledge_bp.route('/document/<int:document_id>', methods=['GET'])
@login_required
def get_document(document_id: int):
    doc = _svc().get_document(document_id, current_user.id)
    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    versions = [
        v.to_dict() for v in
        KnowledgeVersion.query.filter_by(document_id=doc.id)
        .order_by(KnowledgeVersion.version_number.desc()).all()
    ]
    tags = [t.tag for t in KnowledgeTag.query.filter_by(document_id=doc.id).all()]
    collections = [
        cd.collection_id for cd in
        CollectionDocument.query.filter_by(document_id=doc.id).all()
    ]
    data = doc.to_dict()
    data['versions'] = versions
    data['tags'] = tags
    data['collection_ids'] = collections
    latest = KnowledgeVersion.query.filter_by(
        document_id=doc.id, version_number=doc.current_version,
    ).first()
    data['content_preview'] = (latest.content_text or '')[:4000] if latest else ''
    return jsonify({'success': True, 'document': data})


@knowledge_bp.route('/document/<int:document_id>', methods=['PUT'])
@login_required
def update_document(document_id: int):
    svc = _svc()
    doc = svc.get_document(document_id, current_user.id)
    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    data = request.get_json(silent=True) or {}
    try:
        doc = svc.update_document(
            doc,
            user_id=current_user.id,
            title=data.get('title'),
            status=data.get('status'),
            visibility=data.get('visibility'),
            content=data.get('content') or data.get('text'),
            tags=data.get('tags'),
        )
    except PermissionError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 403
    return jsonify({'success': True, 'document': doc.to_dict()})


@knowledge_bp.route('/document/<int:document_id>', methods=['DELETE'])
@login_required
def delete_document(document_id: int):
    svc = _svc()
    doc = svc.get_document(document_id, current_user.id)
    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    hard = request.args.get('hard', '0') in ('1', 'true')
    try:
        svc.delete_document(doc, current_user.id, hard=hard)
    except PermissionError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 403
    return jsonify({'success': True})


@knowledge_bp.route('/document/<int:document_id>/restore/<int:version_number>', methods=['POST'])
@login_required
def restore_version(document_id: int, version_number: int):
    svc = _svc()
    doc = svc.get_document(document_id, current_user.id)
    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    try:
        doc = IngestPipeline().restore_version(doc, version_number, user_id=current_user.id)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    return jsonify({'success': True, 'document': doc.to_dict()})


@knowledge_bp.route('/collections', methods=['GET', 'POST'])
@login_required
def collections():
    svc = _svc()
    org_id = _org_id()
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'collections': svc.list_collections(current_user.id, org_id),
        })
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'name is required'}), 400
    row = svc.create_collection(
        user_id=current_user.id,
        name=name,
        collection_type=data.get('collection_type') or 'workspace',
        description=data.get('description'),
        project_id=data.get('project_id'),
        campaign_id=data.get('campaign_id'),
        organization_id=org_id,
    )
    return jsonify({'success': True, 'collection': row.to_dict()}), 201


@knowledge_bp.route('/reindex', methods=['POST'])
@login_required
def reindex():
    data = request.get_json(silent=True) or {}
    svc = _svc()
    pipeline = IngestPipeline()
    org_id = _org_id()

    if data.get('document_id'):
        doc = svc.get_document(int(data['document_id']), current_user.id)
        if not doc:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        pipeline.reindex_document(doc)
        return jsonify({'success': True, 'reindexed': 1, 'document': doc.to_dict()})

    docs = svc.list_documents(current_user.id, organization_id=org_id, status='active', limit=200)
    count = 0
    for d in docs:
        doc = svc.get_document(d['id'], current_user.id)
        if doc:
            pipeline.reindex_document(doc)
            count += 1
    return jsonify({'success': True, 'reindexed': count})


@knowledge_bp.route('/stats', methods=['GET'])
@login_required
def stats():
    return jsonify({
        'success': True,
        'stats': _svc().stats(current_user.id, _org_id()),
    })
