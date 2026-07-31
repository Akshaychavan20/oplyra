"""
/api/agents/* — AI Agent Framework HTTP surface.

Sits above the Multi-Provider AI Gateway. Does not call providers directly.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.models import Project, Campaign
from app.services.agents.manager import AgentManager
from app.utils.org import get_user_org_id

agents_bp = Blueprint('agents', __name__)


def _manager() -> AgentManager:
    return AgentManager()


def _org_id():
    return get_user_org_id(current_user.id)


def _campaign_accessible(campaign_id, user_id, org_id) -> bool:
    """True if campaign belongs to the user's org or a project they own."""
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return False
    if org_id is not None and campaign.organization_id == org_id:
        return True
    if campaign.project_id:
        project = Project.query.filter_by(id=campaign.project_id, user_id=user_id).first()
        if project:
            return True
    return False


@agents_bp.route('', methods=['GET'])
@agents_bp.route('/', methods=['GET'])
@login_required
def list_agents():
    """GET /api/agents — list available specialized agents."""
    agents = _manager().list_agents()
    return jsonify({'success': True, 'agents': agents})


@agents_bp.route('/run', methods=['POST'])
@login_required
def run_agent():
    """
    POST /api/agents/run

    Body:
      goal (required)
      agent_key | workflow_key | mode=auto
      project_id, campaign_id, brand_voice, extras, provider, model
    """
    data = request.get_json(silent=True) or {}
    goal = (data.get('goal') or data.get('prompt') or '').strip()
    if not goal:
        return jsonify({'success': False, 'error': 'goal is required'}), 400

    agent_key = data.get('agent_key')
    workflow_key = data.get('workflow_key')
    workflow_id = data.get('workflow_id')
    mode = data.get('mode')

    project_id = data.get('project_id')
    campaign_id = data.get('campaign_id')
    org_id = _org_id()

    if project_id:
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()
        if not project:
            return jsonify({'success': False, 'error': 'Client not found'}), 404

    if campaign_id:
        if not _campaign_accessible(campaign_id, current_user.id, org_id):
            return jsonify({'success': False, 'error': 'Campaign not found'}), 404

    try:
        run = _manager().run(
            user_id=current_user.id,
            goal=goal,
            agent_key=agent_key,
            workflow_key=workflow_key,
            workflow_id=workflow_id,
            mode=mode,
            project_id=project_id,
            campaign_id=campaign_id,
            organization_id=org_id,
            brand_voice=data.get('brand_voice'),
            extras=data.get('extras') or data.get('context'),
            provider=data.get('provider'),
            model=data.get('model'),
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'Agent run failed: {exc}'}), 500

    return jsonify({
        'success': True,
        'run': run.to_dict(include_output=True),
    })


@agents_bp.route('/workflows', methods=['GET', 'POST'])
@login_required
def workflows():
    """GET/POST /api/agents/workflows"""
    mgr = _manager()
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'workflows': mgr.list_workflows(user_id=current_user.id),
        })

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    steps = data.get('steps') or []
    if not name:
        return jsonify({'success': False, 'error': 'name is required'}), 400
    if not isinstance(steps, list) or not steps:
        return jsonify({'success': False, 'error': 'steps must be a non-empty list of agent keys'}), 400

    try:
        wf = mgr.create_workflow(
            user_id=current_user.id,
            name=name,
            steps=steps,
            key=data.get('key'),
            description=data.get('description'),
            organization_id=_org_id(),
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    return jsonify({'success': True, 'workflow': wf.to_dict()}), 201


@agents_bp.route('/history', methods=['GET'])
@login_required
def history():
    """GET /api/agents/history?limit=20&status=completed"""
    limit = request.args.get('limit', 20, type=int)
    status = request.args.get('status')
    rows = _manager().list_history(current_user.id, limit=limit, status=status)
    return jsonify({'success': True, 'runs': rows})


@agents_bp.route('/runs/<int:run_id>', methods=['GET'])
@login_required
def get_run(run_id: int):
    """GET /api/agents/runs/:id — poll execution progress / result."""
    run = _manager().get_run(run_id, current_user.id)
    if not run:
        return jsonify({'success': False, 'error': 'Run not found'}), 404
    return jsonify({'success': True, 'run': run.to_dict(include_output=True)})


@agents_bp.route('/status', methods=['GET'])
@login_required
def agents_status():
    """GET /api/agents/status — live agent activity snapshot."""
    return jsonify({
        'success': True,
        'agents': _manager().agent_status_summary(user_id=current_user.id),
    })
