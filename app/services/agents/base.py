"""Base agent — all specialized agents inherit and call AIGateway only."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.services.ai_gateway import AIGateway
from app.services.ai.types import AIRequest, TaskType


class BaseAgent:
    """Enterprise agent base. Never imports provider SDKs — gateway only."""

    key: str = 'base'
    name: str = 'Base Agent'
    task_type: str = 'unknown'
    system_prompt: str = 'You are an Oplyra marketing AI agent.'

    def __init__(self, gateway: Optional[AIGateway] = None):
        self.gateway = gateway or AIGateway()

    def build_prompt(self, goal: str, context: Dict[str, Any]) -> str:
        """Assemble user prompt from goal + agent memory context."""
        sections = [f'## Goal\n{goal.strip()}']

        brand = context.get('brand_voice')
        if brand:
            sections.append(f'## Brand Voice\n{brand}')

        client = context.get('client')
        if client:
            sections.append(f'## Client / Workspace\n{client}')

        campaign = context.get('campaign')
        if campaign:
            sections.append(f'## Campaign\n{campaign}')

        previous = context.get('previous_outputs')
        if previous:
            if isinstance(previous, list):
                joined = '\n\n---\n\n'.join(str(p) for p in previous if p)
            else:
                joined = str(previous)
            if joined.strip():
                sections.append(f'## Previous Agent Outputs\n{joined}')

        history = context.get('prompt_history')
        if history:
            if isinstance(history, list):
                hist = '\n'.join(f'- {h}' for h in history[-8:])
            else:
                hist = str(history)
            if hist.strip():
                sections.append(f'## Prompt History\n{hist}')

        extras = context.get('extras')
        if extras:
            sections.append(f'## Additional Context\n{extras}')

        responsibilities = getattr(self, 'responsibilities', None)
        if responsibilities:
            bullets = '\n'.join(f'- {r}' for r in responsibilities)
            sections.append(
                f'## Your Focus Areas\nCover these responsibilities as relevant:\n{bullets}'
            )

        sections.append(
            '## Output Requirements\n'
            'Return a clear, structured response with headings. '
            'Be specific and actionable for a performance marketing team.'
        )
        return '\n\n'.join(sections)

    def run(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute this agent via the AI Gateway. Returns structured result dict."""
        ctx = context or {}
        prompt = self.build_prompt(goal, ctx)

        try:
            task = TaskType(self.task_type) if self.task_type else TaskType.UNKNOWN
        except ValueError:
            task = TaskType.UNKNOWN

        response = self.gateway.execute(AIRequest(
            prompt=prompt,
            system_instruction=self.system_prompt,
            task_type=task,
            provider=provider or 'auto',
            model=model,
            temperature=temperature if temperature is not None else 0.7,
            user_id=user_id,
            organization_id=organization_id,
            campaign_id=campaign_id,
            skip_cache=True,
            metadata={
                'agent_key': self.key,
                'agent_name': self.name,
            },
        ))

        return {
            'agent_key': self.key,
            'agent_name': self.name,
            'output': response.text,
            'tokens': response.tokens or 0,
            'provider': getattr(response, 'provider', None),
            'model': getattr(response, 'model', None),
            'success': True,
        }

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} key={self.key}>'
