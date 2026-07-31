"""Tool Marketplace — install metadata for future integrations (no real OAuth)."""
from __future__ import annotations

from typing import List, Optional

from app import db
from app.models import ToolDefinition, ToolMarketplaceItem
from app.services.tools.registry import ToolRegistry


class ToolMarketplace:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()

    def list_items(self, *, featured_only: bool = False) -> List[dict]:
        self.registry.ensure_seeded()
        q = ToolMarketplaceItem.query.filter_by(is_available=True)
        if featured_only:
            q = q.filter_by(is_featured=True)
        items = [i.to_dict() for i in q.order_by(ToolMarketplaceItem.name.asc()).all()]
        installed_keys = {
            t.key for t in ToolDefinition.query.filter_by(is_installed=True).all()
        }
        for item in items:
            item['installed'] = item['key'] in installed_keys
        return items

    def install(self, key: str, *, user_id: Optional[int] = None) -> dict:
        """
        Mark marketplace item as installed.
        Does NOT perform OAuth — creates a disabled placeholder ToolDefinition.
        """
        self.registry.ensure_seeded()
        item = ToolMarketplaceItem.query.filter_by(key=key).first()
        if not item:
            raise ValueError(f'Marketplace item not found: {key}')

        tool = ToolDefinition.query.filter_by(key=key).first()
        if not tool:
            tool = ToolDefinition(key=key)
            db.session.add(tool)
        tool.name = item.name
        tool.description = item.description
        tool.category_key = item.category_key or 'integrations'
        tool.version = item.version or '1.0.0'
        tool.provider_type = 'marketplace'
        tool.mcp_server = None
        tool.is_builtin = False
        tool.is_installed = True
        tool.is_enabled = False  # disabled until OAuth connected
        tool.requires_oauth = item.requires_oauth
        tool.icon = item.icon
        tool.meta = {
            'availability': item.availability,
            'publisher': item.publisher,
            'installed_by': user_id,
            'oauth_pending': True,
        }
        item.install_count = (item.install_count or 0) + 1
        db.session.commit()
        return {
            'tool': tool.to_dict(),
            'marketplace': item.to_dict(),
            'message': (
                f'{item.name} installed as a placeholder. '
                'OAuth connection is not implemented in this foundation layer.'
            ),
        }
