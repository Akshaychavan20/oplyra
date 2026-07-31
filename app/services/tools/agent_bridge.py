"""
Agent ↔ Tools bridge.

Wraps AgentManager from OUTSIDE — does not modify the Agent Framework.
Flow: select tools → execute → combine into extras → AgentManager.run() → AI Gateway
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.agents.manager import AgentManager
from app.services.tools.executor import ToolExecutor
from app.services.tools.registry import ToolRegistry
from app.services.tools.types import AGENT_TOOL_MAP, ToolCallRequest


class ToolAgentBridge:
    """External orchestrator: Tools → Agent Manager (unchanged) → Gateway."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[ToolExecutor] = None,
        agent_manager: Optional[AgentManager] = None,
    ):
        self.registry = registry or ToolRegistry()
        self.executor = executor or ToolExecutor(self.registry)
        self.agents = agent_manager or AgentManager()

    def suggested_tools(self, agent_key: Optional[str]) -> List[str]:
        if not agent_key:
            return ['knowledge_search']
        return list(AGENT_TOOL_MAP.get(agent_key, ['knowledge_search']))

    def run_tools(
        self,
        *,
        user_id: int,
        goal: str,
        tool_keys: Optional[List[str]] = None,
        agent_key: Optional[str] = None,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        tool_arguments: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        keys = tool_keys or self.suggested_tools(agent_key)
        tool_arguments = tool_arguments or {}
        context = {
            'user_id': user_id,
            'organization_id': organization_id,
            'project_id': project_id,
            'campaign_id': campaign_id,
        }
        results = []
        for key in keys:
            args = dict(tool_arguments.get(key) or {})
            # Sensible defaults from goal
            if key in ('google_search', 'knowledge_search', 'workspace_search') and 'query' not in args:
                args['query'] = goal
            if key == 'web_browser' and 'url' not in args:
                args['url'] = 'https://example.com'
            if key == 'calculator' and 'expression' not in args:
                continue  # skip unless caller provides expression
            if key == 'file_reader' and 'path' not in args:
                continue
            if key == 'http_request' and 'url' not in args:
                continue

            result = self.executor.execute(
                ToolCallRequest(
                    tool_key=key,
                    arguments=args,
                    user_id=user_id,
                    organization_id=organization_id,
                    agent_key=agent_key,
                ),
                context=context,
            )
            results.append(result.to_dict())
        return results

    def format_tool_context(self, tool_results: List[Dict[str, Any]]) -> str:
        if not tool_results:
            return ''
        parts = ['## Tool Execution Results']
        for r in tool_results:
            status = 'OK' if r.get('success') else 'FAILED'
            parts.append(f"\n### Tool: {r.get('tool_key')} [{status}]")
            if r.get('error'):
                parts.append(f"Error: {r['error']}")
            else:
                parts.append(str(r.get('data')))
        return '\n'.join(parts)

    def run_agent_with_tools(
        self,
        *,
        user_id: int,
        goal: str,
        agent_key: Optional[str] = None,
        workflow_key: Optional[str] = None,
        mode: Optional[str] = None,
        tool_keys: Optional[List[str]] = None,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        brand_voice: Optional[str] = None,
        extras: Optional[str] = None,
        use_tools: bool = True,
    ):
        """
        Execute tools then call AgentManager.run with combined extras.
        Does not modify Agent Framework internals.
        """
        tool_results = []
        if use_tools:
            # For workflow/auto, use research tools as default prep
            effective_agent = agent_key or ('research' if mode == 'auto' or workflow_key else None)
            tool_results = self.run_tools(
                user_id=user_id,
                goal=goal,
                tool_keys=tool_keys,
                agent_key=effective_agent,
                organization_id=organization_id,
                project_id=project_id,
                campaign_id=campaign_id,
            )

        tool_ctx = self.format_tool_context(tool_results)
        combined_extras = extras or ''
        if tool_ctx:
            combined_extras = f'{combined_extras}\n\n{tool_ctx}'.strip() if combined_extras else tool_ctx

        run = self.agents.run(
            user_id=user_id,
            goal=goal,
            agent_key=agent_key,
            workflow_key=workflow_key,
            mode=mode,
            project_id=project_id,
            campaign_id=campaign_id,
            organization_id=organization_id,
            brand_voice=brand_voice,
            extras=combined_extras or None,
        )
        return {
            'agent_run': run.to_dict(include_output=True),
            'tool_results': tool_results,
        }
