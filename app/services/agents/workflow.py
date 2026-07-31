"""Workflow engine — sequential multi-agent execution with shared context."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app import db
from app.models import AgentLog, AgentRun
from app.services.agents.agents import create_agent
from app.services.agents.memory import AgentMemoryService
from app.services.ai_gateway import AIGateway


ProgressCallback = Optional[Callable[[AgentRun], None]]


class WorkflowEngine:
    """Runs an ordered chain of agents, passing previous outputs forward."""

    def __init__(
        self,
        gateway: Optional[AIGateway] = None,
        memory: Optional[AgentMemoryService] = None,
    ):
        self.gateway = gateway or AIGateway()
        self.memory = memory or AgentMemoryService()

    def _log(
        self,
        run: AgentRun,
        event: str,
        message: str = '',
        *,
        agent_key: Optional[str] = None,
        level: str = 'info',
        meta: Optional[dict] = None,
    ) -> None:
        entry = AgentLog(
            run_id=run.id,
            user_id=run.user_id,
            agent_key=agent_key,
            level=level,
            event=event,
            message=message,
        )
        entry.meta = meta or {}
        db.session.add(entry)
        db.session.commit()

    def _update_step(self, run: AgentRun, index: int, **fields) -> None:
        steps = list(run.steps or [])
        if 0 <= index < len(steps):
            steps[index] = {**steps[index], **fields}
            run.steps = steps
            db.session.commit()

    def execute(
        self,
        run: AgentRun,
        agent_keys: List[str],
        goal: str,
        *,
        brand_voice: Optional[str] = None,
        extras: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        on_progress: ProgressCallback = None,
    ) -> AgentRun:
        """Execute agent chain for an existing AgentRun row."""
        run.status = 'running'
        run.started_at = datetime.utcnow()
        run.steps = [
            {
                'agent_key': key,
                'status': 'waiting',
                'output': None,
                'tokens': 0,
                'error': None,
            }
            for key in agent_keys
        ]
        db.session.commit()
        self._log(run, 'started', f'Workflow started with {len(agent_keys)} agents')

        if on_progress:
            on_progress(run)

        base_context = self.memory.build_context(
            user_id=run.user_id,
            goal=goal,
            project_id=run.project_id,
            campaign_id=run.campaign_id,
            brand_voice=brand_voice,
            extras=extras,
        )
        run.context = base_context
        self.memory.record_prompt(
            user_id=run.user_id,
            goal=goal,
            project_id=run.project_id,
            campaign_id=run.campaign_id,
            run_id=run.id,
            organization_id=run.organization_id,
        )
        db.session.commit()

        previous_outputs: List[str] = []
        combined: List[str] = []
        total_tokens = 0

        try:
            for idx, key in enumerate(agent_keys):
                self._update_step(run, idx, status='running')
                self._log(run, 'step_started', f'{key} started', agent_key=key)
                if on_progress:
                    on_progress(run)

                context = {
                    **base_context,
                    'previous_outputs': list(previous_outputs),
                }
                agent = create_agent(key, gateway=self.gateway)
                result = agent.run(
                    goal=goal,
                    context=context,
                    user_id=run.user_id,
                    organization_id=run.organization_id,
                    campaign_id=run.campaign_id,
                    provider=provider,
                    model=model,
                )

                output = result.get('output') or ''
                tokens = int(result.get('tokens') or 0)
                total_tokens += tokens
                previous_outputs.append(f'### {agent.name}\n{output}')
                combined.append(f'## {agent.name}\n\n{output}')

                self._update_step(
                    run,
                    idx,
                    status='completed',
                    output=output,
                    tokens=tokens,
                    provider=result.get('provider'),
                    model=result.get('model'),
                )
                self.memory.record_output(
                    user_id=run.user_id,
                    agent_key=key,
                    output=output,
                    project_id=run.project_id,
                    campaign_id=run.campaign_id,
                    run_id=run.id,
                    organization_id=run.organization_id,
                )
                self._log(
                    run,
                    'step_completed',
                    f'{key} completed ({tokens} tokens)',
                    agent_key=key,
                    meta={'tokens': tokens},
                )
                if on_progress:
                    on_progress(run)

            run.status = 'completed'
            run.final_output = '\n\n'.join(combined)
            run.total_tokens = total_tokens
            run.completed_at = datetime.utcnow()
            db.session.commit()
            self._log(run, 'completed', f'Workflow completed ({total_tokens} tokens)')
        except Exception as exc:
            run.status = 'failed'
            run.error_message = str(exc)[:500]
            run.completed_at = datetime.utcnow()
            run.total_tokens = total_tokens
            # mark current running step as failed
            steps = list(run.steps or [])
            for step in steps:
                if step.get('status') == 'running':
                    step['status'] = 'failed'
                    step['error'] = str(exc)[:300]
            run.steps = steps
            db.session.commit()
            self._log(run, 'failed', str(exc)[:500], level='error')
            raise

        if on_progress:
            on_progress(run)
        return run
