"""Shared types for the Tool Platform."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCallRequest:
    tool_key: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    agent_key: Optional[str] = None
    agent_run_id: Optional[int] = None
    timeout_seconds: float = 30.0
    max_retries: int = 1


@dataclass
class ToolCallResult:
    success: bool
    tool_key: str
    data: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0
    run_id: Optional[int] = None
    mock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'tool_key': self.tool_key,
            'data': self.data,
            'error': self.error,
            'duration_ms': self.duration_ms,
            'retries': self.retries,
            'run_id': self.run_id,
            'mock': self.mock,
        }


# Suggested tools per agent (external bridge; does not modify Agent Framework)
AGENT_TOOL_MAP = {
    'research': ['knowledge_search', 'google_search', 'web_browser'],
    'seo': ['knowledge_search', 'google_search', 'workspace_search'],
    'content': ['knowledge_search', 'workspace_search'],
    'campaign': ['knowledge_search', 'workspace_search', 'calculator'],
    'ads': ['knowledge_search', 'calculator'],
    'analytics': ['workspace_search', 'calculator', 'datetime'],
    'email': ['knowledge_search', 'workspace_search'],
    'social': ['knowledge_search', 'web_browser'],
}
