"""
/api/tools/* — Enterprise Tool Platform HTTP surface.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.services.tools.service import ToolPlatformService
from app.utils.org import get_user_org_id, user_is_org_admin

tools_bp = Blueprint('tools', __name__)


def _svc() -> ToolPlatformService:
    return ToolPlatformService()


def _org_id():
    return get_user_org_id(current_user.id)


def _require_org_admin():
    org_id = _org_id()
    if not user_is_org_admin(current_user.id, org_id):
        return jsonify({'success': False, 'error': 'Admin role required'}), 403
    return None


@tools_bp.route('', methods=['GET'])
@tools_bp.route('/', methods=['GET'])
@login_required
def list_tools():
    q = (request.args.get('q') or '').strip()
    enabled = request.args.get('enabled')
    svc = _svc()
    if q:
        tools = svc.registry.discover(q)
    else:
        tools = svc.list_tools(
            installed_only=True,
            enabled_only=(enabled == '1'),
        )
    return jsonify({
        'success': True,
        'tools': tools,
        'mcp_tools': svc.mcp_list_tools(),
    })


@tools_bp.route('/run', methods=['POST'])
@login_required
def run_tool():
    """
    POST /api/tools/run
    Body: { tool_key, arguments?, agent_key?, use_agent?: bool, goal? }
    If use_agent=true and goal provided → ToolAgentBridge path.
    """
    from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
    try:
        enforce_rate_limit('tool_run', identity=f'user:{current_user.id}', organization_id=_org_id())
    except RateLimitExceeded as exc:
        return jsonify({'success': False, 'error': str(exc), 'error_code': 'RATE_LIMITED'}), 429
    data = request.get_json(silent=True) or {}
    svc = _svc()

    if data.get('use_agent') and data.get('goal'):
        result = svc.run_agent_with_tools(
            user_id=current_user.id,
            goal=data['goal'],
            agent_key=data.get('agent_key'),
            workflow_key=data.get('workflow_key'),
            mode=data.get('mode'),
            tool_keys=data.get('tool_keys'),
            organization_id=_org_id(),
            project_id=data.get('project_id'),
            campaign_id=data.get('campaign_id'),
            brand_voice=data.get('brand_voice'),
            extras=data.get('extras'),
            use_tools=True,
        )
        return jsonify({'success': True, **result})

    tool_key = data.get('tool_key') or data.get('key')
    if not tool_key:
        return jsonify({'success': False, 'error': 'tool_key is required'}), 400

    result = svc.run_tool(
        tool_key=tool_key,
        arguments=data.get('arguments') or data.get('args') or {},
        user_id=current_user.id,
        organization_id=_org_id(),
        agent_key=data.get('agent_key'),
        timeout_seconds=float(data.get('timeout_seconds') or 30),
        max_retries=int(data.get('max_retries') or 1),
    )
    status = 200 if result.get('success') else 400
    return jsonify({'success': result.get('success'), 'result': result}), status


@tools_bp.route('/categories', methods=['GET'])
@login_required
def categories():
    return jsonify({'success': True, 'categories': _svc().list_categories()})


@tools_bp.route('/history', methods=['GET'])
@login_required
def history():
    limit = request.args.get('limit', 30, type=int)
    return jsonify({'success': True, 'runs': _svc().history(current_user.id, limit=limit)})


@tools_bp.route('/runs/<int:run_id>/logs', methods=['GET'])
@login_required
def run_logs(run_id: int):
    return jsonify({'success': True, 'logs': _svc().run_logs(run_id, current_user.id)})


@tools_bp.route('/marketplace', methods=['GET'])
@login_required
def marketplace():
    featured = request.args.get('featured') == '1'
    return jsonify({
        'success': True,
        'items': _svc().list_marketplace(featured_only=featured),
    })


@tools_bp.route('/install', methods=['POST'])
@login_required
def install():
    data = request.get_json(silent=True) or {}
    key = data.get('key') or data.get('tool_key')
    if not key:
        return jsonify({'success': False, 'error': 'key is required'}), 400
    try:
        result = _svc().install(key, current_user.id)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    return jsonify({'success': True, **result}), 201


@tools_bp.route('/<tool_key>/enable', methods=['POST'])
@login_required
def enable_tool(tool_key: str):
    denied = _require_org_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    row = _svc().set_enabled(tool_key, bool(enabled))
    if not row:
        return jsonify({'success': False, 'error': 'Tool not found'}), 404
    return jsonify({'success': True, 'tool': row})


@tools_bp.route('/permissions', methods=['GET', 'POST'])
@login_required
def permissions():
    svc = _svc()
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'permissions': svc.list_permissions(organization_id=_org_id()),
        })
    denied = _require_org_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    if not data.get('tool_key'):
        return jsonify({'success': False, 'error': 'tool_key is required'}), 400
    perm = svc.add_permission(
        tool_key=data['tool_key'],
        effect=data.get('effect') or 'allow',
        user_id=data.get('user_id'),
        organization_id=_org_id(),
        role=data.get('role'),
        oauth_scopes=data.get('oauth_scopes'),
    )
    return jsonify({'success': True, 'permission': perm}), 201
