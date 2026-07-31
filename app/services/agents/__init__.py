"""
AI Agent Framework — sits ABOVE the Multi-Provider AI Gateway.

Agents never call LLM providers directly. All generation goes through AIGateway.
"""
from app.services.agents.manager import AgentManager
from app.services.agents.catalog import AGENT_CATALOG, DEFAULT_WORKFLOWS

__all__ = ['AgentManager', 'AGENT_CATALOG', 'DEFAULT_WORKFLOWS']
