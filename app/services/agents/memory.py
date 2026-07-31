"""Agent memory — workspace, campaign, client, brand voice, previous outputs, prompt history."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import db
from app.models import AgentMemory, Campaign, Project


class AgentMemoryService:
    """Load and persist contextual memory for agent runs."""

    MEMORY_TYPES = (
        'workspace',
        'campaign',
        'client',
        'brand_voice',
        'previous_output',
        'prompt_history',
    )

    def save(
        self,
        *,
        user_id: int,
        memory_type: str,
        key: str,
        value: Any,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        agent_key: Optional[str] = None,
        run_id: Optional[int] = None,
    ) -> AgentMemory:
        if memory_type not in self.MEMORY_TYPES:
            raise ValueError(f'Invalid memory_type: {memory_type}')

        row = AgentMemory.query.filter_by(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            project_id=project_id,
            campaign_id=campaign_id,
            agent_key=agent_key,
        ).order_by(AgentMemory.id.desc()).first()

        if row and memory_type in ('brand_voice', 'workspace', 'client'):
            row.value = value
            row.run_id = run_id or row.run_id
            row.organization_id = organization_id or row.organization_id
        else:
            row = AgentMemory(
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                campaign_id=campaign_id,
                memory_type=memory_type,
                agent_key=agent_key,
                run_id=run_id,
                key=key,
            )
            row.value = value
            db.session.add(row)

        db.session.commit()
        return row

    def build_context(
        self,
        *,
        user_id: int,
        goal: str,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        brand_voice: Optional[str] = None,
        extras: Optional[str] = None,
        previous_outputs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Assemble the memory bundle every agent receives."""
        ctx: Dict[str, Any] = {
            'brand_voice': brand_voice or '',
            'client': '',
            'campaign': '',
            'workspace': '',
            'previous_outputs': previous_outputs or [],
            'prompt_history': [],
            'extras': extras or '',
        }

        if project_id:
            project = Project.query.filter_by(id=project_id, user_id=user_id).first()
            if project:
                parts = [f'Client: {project.name}']
                if project.description:
                    parts.append(project.description)
                if project.category:
                    parts.append(f'Category: {project.category}')
                ctx['client'] = '\n'.join(parts)
                ctx['workspace'] = ctx['client']

        if campaign_id:
            campaign = Campaign.query.get(campaign_id)
            if campaign:
                parts = [
                    f'Campaign: {campaign.name}',
                    f'Type: {campaign.type}',
                    f'Status: {campaign.status}',
                    f'Stage: {campaign.current_stage}',
                ]
                if campaign.description:
                    parts.append(campaign.description)
                if campaign.budget is not None:
                    parts.append(f'Budget: {campaign.budget} {campaign.currency or ""}')
                ctx['campaign'] = '\n'.join(parts)

        # Stored brand voice (explicit arg wins)
        if not ctx['brand_voice']:
            mem = (
                AgentMemory.query.filter_by(
                    user_id=user_id,
                    memory_type='brand_voice',
                    project_id=project_id,
                )
                .order_by(AgentMemory.updated_at.desc())
                .first()
            )
            if not mem and project_id:
                mem = (
                    AgentMemory.query.filter_by(
                        user_id=user_id,
                        memory_type='brand_voice',
                        project_id=None,
                    )
                    .order_by(AgentMemory.updated_at.desc())
                    .first()
                )
            if mem:
                val = mem.value
                ctx['brand_voice'] = val if isinstance(val, str) else str(val)

        # Recent prompt history for this user/project
        history_rows = (
            AgentMemory.query.filter_by(user_id=user_id, memory_type='prompt_history')
            .filter(
                (AgentMemory.project_id == project_id) if project_id else True
            )
            .order_by(AgentMemory.id.desc())
            .limit(8)
            .all()
        )
        ctx['prompt_history'] = [
            (r.value if isinstance(r.value, str) else str(r.value)) for r in reversed(history_rows)
        ]
        if goal and (not ctx['prompt_history'] or ctx['prompt_history'][-1] != goal):
            ctx['prompt_history'].append(goal)

        # Additive Knowledge Engine RAG hook (optional — never breaks agents)
        try:
            from app.services.knowledge.rag import inject_rag_into_context
            inject_rag_into_context(
                ctx,
                user_id=user_id,
                goal=goal,
                project_id=project_id,
                campaign_id=campaign_id,
            )
        except Exception:
            pass

        return ctx

    def record_prompt(
        self,
        *,
        user_id: int,
        goal: str,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        run_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ) -> None:
        self.save(
            user_id=user_id,
            memory_type='prompt_history',
            key=f'prompt_{run_id or "adhoc"}',
            value=goal,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            run_id=run_id,
        )

    def record_output(
        self,
        *,
        user_id: int,
        agent_key: str,
        output: str,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        run_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ) -> None:
        self.save(
            user_id=user_id,
            memory_type='previous_output',
            key=f'{agent_key}_{run_id or "adhoc"}',
            value=output,
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            agent_key=agent_key,
            run_id=run_id,
        )
