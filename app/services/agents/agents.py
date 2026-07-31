"""Concrete specialized agents — thin subclasses over BaseAgent + catalog metadata."""
from __future__ import annotations

from typing import Dict, List, Type

from app.services.agents.base import BaseAgent
from app.services.agents.catalog import AGENT_CATALOG


def _make_agent_class(spec: dict) -> Type[BaseAgent]:
    class_name = ''.join(part.capitalize() for part in spec['key'].split('_')) + 'Agent'

    class _Agent(BaseAgent):
        key = spec['key']
        name = spec['name']
        task_type = spec.get('task_type') or 'unknown'
        system_prompt = spec.get('system_prompt') or BaseAgent.system_prompt
        responsibilities = spec.get('responsibilities') or []
        description = spec.get('description') or ''
        category = spec.get('category') or ''
        icon = spec.get('icon') or 'bi-robot'

    _Agent.__name__ = class_name
    _Agent.__qualname__ = class_name
    return _Agent


# Build one class per catalog entry
_AGENT_CLASSES: Dict[str, Type[BaseAgent]] = {
    spec['key']: _make_agent_class(spec) for spec in AGENT_CATALOG
}

ResearchAgent = _AGENT_CLASSES['research']
SEOAgent = _AGENT_CLASSES['seo']
ContentAgent = _AGENT_CLASSES['content']
CampaignAgent = _AGENT_CLASSES['campaign']
AdsAgent = _AGENT_CLASSES['ads']
AnalyticsAgent = _AGENT_CLASSES['analytics']
EmailAgent = _AGENT_CLASSES['email']
SocialMediaAgent = _AGENT_CLASSES['social']


def get_agent_class(key: str) -> Type[BaseAgent]:
    cls = _AGENT_CLASSES.get(key)
    if not cls:
        raise KeyError(f'Unknown agent key: {key}')
    return cls


def create_agent(key: str, gateway=None) -> BaseAgent:
    return get_agent_class(key)(gateway=gateway)


def all_agent_keys() -> List[str]:
    return [s['key'] for s in AGENT_CATALOG]


__all__ = [
    'ResearchAgent',
    'SEOAgent',
    'ContentAgent',
    'CampaignAgent',
    'AdsAgent',
    'AnalyticsAgent',
    'EmailAgent',
    'SocialMediaAgent',
    'get_agent_class',
    'create_agent',
    'all_agent_keys',
]
