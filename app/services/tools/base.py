"""Base tool interface + MCP abstraction (provider-agnostic)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseTool(ABC):
    """Production-ready tool interface. Implementations may be stubs or live."""

    key: str = 'base'
    name: str = 'Base Tool'
    description: str = ''
    category_key: str = 'general'
    version: str = '1.0.0'
    provider_type: str = 'builtin'
    mcp_server: Optional[str] = 'local'
    requires_oauth: bool = False
    icon: str = 'bi-wrench'
    input_schema: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a structured dict result. Must not raise for expected failures."""
        raise NotImplementedError

    def validate(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Return error string if invalid, else None."""
        required = (self.input_schema or {}).get('required') or []
        for field in required:
            if field not in (arguments or {}):
                return f'Missing required argument: {field}'
        return None


class MCPServer(ABC):
    """Model Context Protocol server abstraction — never couple to one vendor."""

    server_id: str = 'base'
    display_name: str = 'Base MCP Server'

    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def call_tool(self, tool_key: str, arguments: Dict[str, Any], *, context: Optional[Dict] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        return {'server_id': self.server_id, 'status': 'ok'}


class LocalMCPServer(MCPServer):
    """In-process MCP server that dispatches to registered BaseTool instances."""

    server_id = 'local'
    display_name = 'Oplyra Local MCP'

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.key] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                'key': t.key,
                'name': t.name,
                'description': t.description,
                'input_schema': t.input_schema,
                'mcp_server': self.server_id,
            }
            for t in self._tools.values()
        ]

    def call_tool(self, tool_key: str, arguments: Dict[str, Any], *, context: Optional[Dict] = None) -> Dict[str, Any]:
        tool = self._tools.get(tool_key)
        if not tool:
            return {'success': False, 'error': f'Tool not found on MCP server: {tool_key}'}
        err = tool.validate(arguments or {})
        if err:
            return {'success': False, 'error': err}
        result = tool.execute(arguments or {}, context=context)
        if isinstance(result, dict) and 'success' in result:
            return result
        return {'success': True, 'data': result, 'mock': True}


class FutureMCPServer(MCPServer):
    """Placeholder for remote MCP servers (stdio/SSE/HTTP) — not wired yet."""

    def __init__(self, server_id: str, display_name: str = ''):
        self.server_id = server_id
        self.display_name = display_name or server_id

    def list_tools(self) -> List[Dict[str, Any]]:
        return []

    def call_tool(self, tool_key: str, arguments: Dict[str, Any], *, context: Optional[Dict] = None) -> Dict[str, Any]:
        return {
            'success': False,
            'error': f'Remote MCP server "{self.server_id}" is not connected yet.',
            'mock': True,
        }
