"""
Agent Manager — selects agents, chains workflows, passes context, combines outputs.

Public facade for the Agent Framework. Callers should use this, not individual agents.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models import AgentDefinition, AgentRun, AgentWorkflow
from app.services.agents.catalog import (
    AGENT_CATALOG,
    AUTO_AGENT_CHAIN,
    DEFAULT_WORKFLOWS,
)
from app.services.agents.memory import AgentMemoryService
from app.services.agents.workflow import WorkflowEngine
from app.services.ai_gateway import AIGateway


class AgentManager:
    """Orchestrates single-agent and multi-agent execution above the AI Gateway."""

    def __init__(self, gateway: Optional[AIGateway] = None):
        self.gateway = gateway or AIGateway()
        self.memory = AgentMemoryService()
        self.workflow_engine = WorkflowEngine(gateway=self.gateway, memory=self.memory)

    # ── Bootstrap / catalog ──────────────────────────────────────────────────

    def ensure_seeded(self) -> None:
        """Idempotently seed agent definitions and system workflows."""
        existing = {a.key for a in AgentDefinition.query.all()}
        for spec in AGENT_CATALOG:
            if spec['key'] in existing:
                continue
            db.session.add(AgentDefinition(
                key=spec['key'],
                name=spec['name'],
                description=spec['description'],
                category=spec.get('category'),
                icon=spec.get('icon'),
                task_type=spec.get('task_type'),
                system_prompt=spec.get('system_prompt'),
                is_active=True,
                sort_order=spec.get('sort_order', 0),
            ))
        db.session.commit()

        existing_wf = {w.key for w in AgentWorkflow.query.filter_by(is_system=True).all()}
        for wf in DEFAULT_WORKFLOWS:
            if wf['key'] in existing_wf:
                continue
            row = AgentWorkflow(
                user_id=None,
                key=wf['key'],
                name=wf['name'],
                description=wf.get('description'),
                is_system=True,
                is_active=True,
            )
            row.steps = wf['steps']
            db.session.add(row)
        db.session.commit()

    def list_agents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        self.ensure_seeded()
        q = AgentDefinition.query.order_by(AgentDefinition.sort_order.asc())
        if active_only:
            q = q.filter_by(is_active=True)
        agents = [a.to_dict() for a in q.all()]
        # Enrich with catalog responsibilities (not stored in DB)
        by_key = {s['key']: s for s in AGENT_CATALOG}
        for a in agents:
            spec = by_key.get(a['key']) or {}
            a['responsibilities'] = spec.get('responsibilities') or []
        return agents

    def list_workflows(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        self.ensure_seeded()
        q = AgentWorkflow.query.filter_by(is_active=True)
        rows = q.order_by(AgentWorkflow.is_system.desc(), AgentWorkflow.name.asc()).all()
        result = []
        for w in rows:
            if w.is_system or (user_id and w.user_id == user_id) or w.user_id is None:
                result.append(w.to_dict())
        return result

    def create_workflow(
        self,
        *,
        user_id: int,
        name: str,
        steps: List[str],
        key: Optional[str] = None,
        description: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> AgentWorkflow:
        self.ensure_seeded()
        valid = {a['key'] for a in AGENT_CATALOG}
        cleaned = [s for s in steps if s in valid]
        if not cleaned:
            raise ValueError('Workflow must include at least one valid agent key')
        slug = (key or name).lower().replace(' ', '_')[:80]
        row = AgentWorkflow(
            user_id=user_id,
            organization_id=organization_id,
            key=slug,
            name=name,
            description=description,
            is_system=False,
            is_active=True,
        )
        row.steps = cleaned
        db.session.add(row)
        db.session.commit()
        return row

    # ── Execution ────────────────────────────────────────────────────────────

    def run(
        self,
        *,
        user_id: int,
        goal: str,
        agent_key: Optional[str] = None,
        workflow_key: Optional[str] = None,
        workflow_id: Optional[int] = None,
        mode: Optional[str] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        brand_voice: Optional[str] = None,
        extras: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AgentRun:
        """
        Select and run agent(s).

        Modes:
          - agent_key set → single agent
          - workflow_key / workflow_id → named workflow
          - mode='auto' or neither → Auto Full Funnel chain
        """
        self.ensure_seeded()
        if not goal or not str(goal).strip():
            raise ValueError('goal is required')

        resolved_mode = mode or 'single'
        agent_keys: List[str] = []
        workflow_row: Optional[AgentWorkflow] = None

        if agent_key and not workflow_key and not workflow_id and mode != 'auto':
            valid = {a['key'] for a in AGENT_CATALOG}
            if agent_key not in valid:
                raise ValueError(f'Unknown agent: {agent_key}')
            agent_keys = [agent_key]
            resolved_mode = 'single'
        elif workflow_id or workflow_key:
            if workflow_id:
                workflow_row = AgentWorkflow.query.get(workflow_id)
            else:
                workflow_row = AgentWorkflow.query.filter_by(key=workflow_key, is_active=True).first()
            if not workflow_row:
                raise ValueError('Workflow not found')
            agent_keys = list(workflow_row.steps)
            resolved_mode = 'workflow'
        else:
            # Auto Agent
            agent_keys = list(AUTO_AGENT_CHAIN)
            workflow_row = AgentWorkflow.query.filter_by(key='auto_full_funnel').first()
            resolved_mode = 'auto'

        if not agent_keys:
            raise ValueError('No agents to run')

        if brand_voice:
            self.memory.save(
                user_id=user_id,
                memory_type='brand_voice',
                key='default',
                value=brand_voice,
                organization_id=organization_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )

        run = AgentRun(
            user_id=user_id,
            organization_id=organization_id,
            workflow_id=workflow_row.id if workflow_row else None,
            agent_key=agent_keys[0] if len(agent_keys) == 1 else None,
            mode=resolved_mode,
            status='pending',
            project_id=project_id,
            campaign_id=campaign_id,
        )
        run.input_payload = {
            'goal': goal,
            'agent_keys': agent_keys,
            'brand_voice': brand_voice,
            'extras': extras,
            'provider': provider,
            'model': model,
        }
        db.session.add(run)
        db.session.commit()

        return self.workflow_engine.execute(
            run,
            agent_keys,
            goal.strip(),
            brand_voice=brand_voice,
            extras=extras,
            provider=provider,
            model=model,
        )

    def get_run(self, run_id: int, user_id: int) -> Optional[AgentRun]:
        return AgentRun.query.filter_by(id=run_id, user_id=user_id).first()

    def list_history(
        self,
        user_id: int,
        *,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = AgentRun.query.filter_by(user_id=user_id)
        if status:
            q = q.filter_by(status=status)
        rows = q.order_by(AgentRun.created_at.desc()).limit(min(limit, 100)).all()
        return [r.to_dict(include_output=True) for r in rows]

    def agent_status_summary(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Status snapshot for UI / enterprise compatibility."""
        self.ensure_seeded()
        agents = self.list_agents()
        summary = []
        for a in agents:
            q = AgentRun.query
            if user_id:
                q = q.filter_by(user_id=user_id)
            # Prefer runs that targeted this agent (single) or include it in steps JSON
            candidates = q.order_by(AgentRun.created_at.desc()).limit(40).all()
            last = None
            for run in candidates:
                if run.agent_key == a['key']:
                    last = run
                    break
                keys = [s.get('agent_key') for s in (run.steps or [])]
                if a['key'] in keys:
                    last = run
                    break
            status = 'idle'
            last_run = None
            logs = a.get('description') or ''
            if last:
                last_run = last.completed_at or last.created_at
                if last.status == 'running':
                    status = 'active'
                logs = (last.final_output or last.error_message or logs)[:240]
            summary.append({
                'key': a['key'],
                'name': a['name'],
                'goal': a['description'],
                'status': status,
                'last_run': last_run.isoformat() if last_run else None,
                'logs': logs,
            })
        return summary
