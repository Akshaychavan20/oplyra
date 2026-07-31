"""Tool Platform facade."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models import ToolRun, ToolLog, ToolPermission
from app.services.tools.agent_bridge import ToolAgentBridge
from app.services.tools.executor import ToolExecutor
from app.services.tools.marketplace import ToolMarketplace
from app.services.tools.permissions import get_user_org_id, grant_permission
from app.services.tools.registry import ToolRegistry
from app.services.tools.types import ToolCallRequest


class ToolPlatformService:
    def __init__(self):
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self.registry)
        self.marketplace = ToolMarketplace(self.registry)
        self.bridge = ToolAgentBridge(self.registry, self.executor)

    def list_tools(self, **kwargs) -> List[dict]:
        return self.registry.list_tools(**kwargs)

    def list_categories(self) -> List[dict]:
        return self.registry.list_categories()

    def run_tool(
        self,
        *,
        tool_key: str,
        arguments: Optional[dict] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        agent_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        org_id = organization_id or (get_user_org_id(user_id) if user_id else None)
        result = self.executor.execute(
            ToolCallRequest(
                tool_key=tool_key,
                arguments=arguments or {},
                user_id=user_id,
                organization_id=org_id,
                agent_key=agent_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            ),
            context={
                'user_id': user_id,
                'organization_id': org_id,
            },
        )
        return result.to_dict()

    def history(self, user_id: int, *, limit: int = 30) -> List[dict]:
        rows = (
            ToolRun.query.filter_by(user_id=user_id)
            .order_by(ToolRun.created_at.desc())
            .limit(min(limit, 100))
            .all()
        )
        return [r.to_dict(include_io=True) for r in rows]

    def run_logs(self, run_id: int, user_id: int) -> List[dict]:
        run = ToolRun.query.filter_by(id=run_id, user_id=user_id).first()
        if not run:
            return []
        return [l.to_dict() for l in ToolLog.query.filter_by(run_id=run_id).order_by(ToolLog.id.asc()).all()]

    def list_marketplace(self, **kwargs) -> List[dict]:
        return self.marketplace.list_items(**kwargs)

    def install(self, key: str, user_id: int) -> dict:
        return self.marketplace.install(key, user_id=user_id)

    def set_enabled(self, key: str, enabled: bool) -> Optional[dict]:
        row = self.registry.set_enabled(key, enabled)
        return row.to_dict() if row else None

    def list_permissions(self, organization_id: Optional[int] = None) -> List[dict]:
        q = ToolPermission.query
        if organization_id:
            q = q.filter_by(organization_id=organization_id)
        return [p.to_dict() for p in q.order_by(ToolPermission.id.desc()).limit(100).all()]

    def add_permission(self, **kwargs) -> dict:
        return grant_permission(**kwargs).to_dict()

    def run_agent_with_tools(self, **kwargs):
        return self.bridge.run_agent_with_tools(**kwargs)

    def mcp_list_tools(self) -> List[dict]:
        self.registry.ensure_seeded()
        return self.registry.mcp.list_tools()
