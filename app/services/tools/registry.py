"""Tool Registry — discovery, enable/disable, categories, versioning, seeding."""
from __future__ import annotations

from typing import Dict, List, Optional

from app import db
from app.models import ToolCategory, ToolDefinition, ToolMarketplaceItem
from app.services.tools.base import BaseTool, LocalMCPServer
from app.services.tools.builtins import get_builtin_tools


CATEGORIES = [
    ('search', 'Search', 'Web and knowledge search tools', 'bi-search', 10),
    ('web', 'Web', 'Browsing and HTTP tools', 'bi-globe2', 20),
    ('knowledge', 'Knowledge', 'RAG and document tools', 'bi-journal-richtext', 30),
    ('workspace', 'Workspace', 'Clients, campaigns, and org data', 'bi-briefcase', 40),
    ('utility', 'Utility', 'Calculator, date/time, helpers', 'bi-tools', 50),
    ('files', 'Files', 'File readers and storage tools', 'bi-folder2', 60),
    ('developer', 'Developer', 'HTTP and developer utilities', 'bi-code-slash', 70),
    ('integrations', 'Integrations', 'Marketplace integrations', 'bi-plug', 80),
]

MARKETPLACE_CATALOG = [
    ('google', 'Google Workspace', 'Drive, Docs, Sheets, Calendar, Search Console, GA4', 'Google', 'integrations', True),
    ('slack', 'Slack', 'Channels, messages, and notifications', 'Slack', 'integrations', True),
    ('hubspot', 'HubSpot', 'CRM, marketing automation, contacts', 'HubSpot', 'integrations', True),
    ('salesforce', 'Salesforce', 'CRM and opportunity tooling', 'Salesforce', 'integrations', True),
    ('notion', 'Notion', 'Pages, databases, and knowledge sync', 'Notion', 'integrations', True),
    ('wordpress', 'WordPress', 'Posts, pages, and media publishing', 'WordPress', 'integrations', True),
    ('shopify', 'Shopify', 'Products, orders, and storefronts', 'Shopify', 'integrations', True),
    ('meta', 'Meta', 'Facebook & Instagram Ads', 'Meta', 'integrations', True),
    ('zapier', 'Zapier', 'Automation bridge to 5000+ apps', 'Zapier', 'integrations', True),
    ('github', 'GitHub', 'Repos, issues, and pull requests', 'GitHub', 'integrations', True),
    ('discord', 'Discord', 'Servers, channels, and bots', 'Discord', 'integrations', True),
    ('dropbox', 'Dropbox', 'Cloud file sync', 'Dropbox', 'integrations', False),
    ('onedrive', 'OneDrive', 'Microsoft cloud files', 'Microsoft', 'integrations', False),
    ('woocommerce', 'WooCommerce', 'WordPress e-commerce', 'WooCommerce', 'integrations', False),
]


class ToolRegistry:
    """In-memory + DB-backed registry with Local MCP server."""

    def __init__(self):
        self._runtime: Dict[str, BaseTool] = {}
        self.mcp = LocalMCPServer()
        for tool in get_builtin_tools():
            self._runtime[tool.key] = tool
            self.mcp.register(tool)

    def ensure_seeded(self) -> None:
        for key, name, desc, icon, order in CATEGORIES:
            if not ToolCategory.query.filter_by(key=key).first():
                db.session.add(ToolCategory(
                    key=key, name=name, description=desc, icon=icon, sort_order=order,
                ))
        db.session.commit()

        for tool in get_builtin_tools():
            row = ToolDefinition.query.filter_by(key=tool.key).first()
            if not row:
                row = ToolDefinition(key=tool.key)
                db.session.add(row)
            row.name = tool.name
            row.description = tool.description
            row.category_key = tool.category_key
            row.version = tool.version
            row.provider_type = tool.provider_type
            row.mcp_server = tool.mcp_server
            row.is_builtin = True
            row.is_installed = True
            row.is_enabled = True if row.is_enabled is None else row.is_enabled
            row.requires_oauth = tool.requires_oauth
            row.icon = tool.icon
            row.input_schema = tool.input_schema
        db.session.commit()

        for key, name, desc, publisher, cat, featured in MARKETPLACE_CATALOG:
            item = ToolMarketplaceItem.query.filter_by(key=key).first()
            if not item:
                item = ToolMarketplaceItem(key=key)
                db.session.add(item)
            item.name = name
            item.description = desc
            item.publisher = publisher
            item.category_key = cat
            item.icon = 'bi-plugin'
            item.requires_oauth = True
            item.is_featured = featured
            item.is_available = True
            item.availability = 'coming_soon'
        db.session.commit()

    def get_runtime(self, key: str) -> Optional[BaseTool]:
        return self._runtime.get(key)

    def list_tools(self, *, installed_only: bool = True, enabled_only: bool = False) -> List[dict]:
        self.ensure_seeded()
        q = ToolDefinition.query.order_by(ToolDefinition.name.asc())
        if installed_only:
            q = q.filter_by(is_installed=True)
        if enabled_only:
            q = q.filter_by(is_enabled=True)
        return [t.to_dict() for t in q.all()]

    def list_categories(self) -> List[dict]:
        self.ensure_seeded()
        return [c.to_dict() for c in ToolCategory.query.order_by(ToolCategory.sort_order).all()]

    def set_enabled(self, key: str, enabled: bool) -> Optional[ToolDefinition]:
        self.ensure_seeded()
        row = ToolDefinition.query.filter_by(key=key).first()
        if not row:
            return None
        row.is_enabled = bool(enabled)
        db.session.commit()
        return row

    def discover(self, query: str = '') -> List[dict]:
        tools = self.list_tools(installed_only=True)
        if not query:
            return tools
        q = query.lower()
        return [
            t for t in tools
            if q in (t.get('name') or '').lower()
            or q in (t.get('description') or '').lower()
            or q in (t.get('key') or '').lower()
        ]
