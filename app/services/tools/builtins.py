"""Built-in stub tools — production interfaces with mock/demo responses."""
from __future__ import annotations

import datetime as dt
import math
import operator
import re
from typing import Any, Dict, List, Optional

from app.services.tools.base import BaseTool


class GoogleSearchTool(BaseTool):
    key = 'google_search'
    name = 'Google Search'
    description = 'Search the web via Google (stub — returns mock SERP results).'
    category_key = 'search'
    icon = 'bi-google'
    input_schema = {
        'type': 'object',
        'properties': {'query': {'type': 'string'}, 'num_results': {'type': 'integer'}},
        'required': ['query'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        q = arguments.get('query', '')
        n = int(arguments.get('num_results') or 3)
        results = [
            {
                'title': f'Mock result {i + 1} for "{q}"',
                'url': f'https://example.com/search?q={i + 1}',
                'snippet': f'Demo SERP snippet about {q}. Not a live Google result.',
            }
            for i in range(max(1, min(n, 5)))
        ]
        return {'success': True, 'mock': True, 'data': {'query': q, 'results': results}}


class WebBrowserTool(BaseTool):
    key = 'web_browser'
    name = 'Web Browser'
    description = 'Fetch and summarize a web page (stub).'
    category_key = 'web'
    icon = 'bi-globe2'
    input_schema = {
        'type': 'object',
        'properties': {'url': {'type': 'string'}},
        'required': ['url'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = arguments.get('url', '')
        return {
            'success': True,
            'mock': True,
            'data': {
                'url': url,
                'title': 'Mock Page Title',
                'text': f'Demo page content extracted from {url}. Live browsing not enabled.',
                'status_code': 200,
            },
        }


class HttpRequestTool(BaseTool):
    key = 'http_request'
    name = 'HTTP Request'
    description = 'Perform an HTTP request (stub — does not call external networks).'
    category_key = 'developer'
    icon = 'bi-hdd-network'
    input_schema = {
        'type': 'object',
        'properties': {
            'method': {'type': 'string'},
            'url': {'type': 'string'},
            'headers': {'type': 'object'},
            'body': {},
        },
        'required': ['url'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        method = (arguments.get('method') or 'GET').upper()
        url = arguments.get('url', '')
        return {
            'success': True,
            'mock': True,
            'data': {
                'method': method,
                'url': url,
                'status_code': 200,
                'body': {'message': 'Mock HTTP response — live requests disabled in foundation layer.'},
            },
        }


class CalculatorTool(BaseTool):
    key = 'calculator'
    name = 'Calculator'
    description = 'Evaluate a safe arithmetic expression.'
    category_key = 'utility'
    icon = 'bi-calculator'
    input_schema = {
        'type': 'object',
        'properties': {'expression': {'type': 'string'}},
        'required': ['expression'],
    }

    _OPS = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '**': operator.pow,
        '%': operator.mod,
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        expr = str(arguments.get('expression') or '').strip()
        if not expr or not re.fullmatch(r'[\d\s\.\+\-\*\/\%\(\)]+', expr):
            return {'success': False, 'error': 'Invalid or unsafe expression', 'mock': False}
        try:
            # Restricted eval via AST would be better; use simple safe subset
            result = eval(expr, {'__builtins__': {}}, {'math': math})  # noqa: S307 — sanitized pattern above
            return {'success': True, 'mock': False, 'data': {'expression': expr, 'result': result}}
        except Exception as exc:
            return {'success': False, 'error': str(exc), 'mock': False}


class DateTimeTool(BaseTool):
    key = 'datetime'
    name = 'Date & Time'
    description = 'Return current UTC date/time and simple formatting helpers.'
    category_key = 'utility'
    icon = 'bi-calendar3'
    input_schema = {
        'type': 'object',
        'properties': {'timezone': {'type': 'string'}, 'format': {'type': 'string'}},
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = dt.datetime.utcnow()
        fmt = arguments.get('format') or '%Y-%m-%d %H:%M:%S'
        try:
            formatted = now.strftime(fmt)
        except Exception:
            formatted = now.isoformat()
        return {
            'success': True,
            'mock': False,
            'data': {
                'utc_iso': now.isoformat() + 'Z',
                'formatted': formatted,
                'timezone': arguments.get('timezone') or 'UTC',
                'unix': int(now.timestamp()),
            },
        }


class FileReaderTool(BaseTool):
    key = 'file_reader'
    name = 'File Reader'
    description = 'Read a workspace file path (stub — returns mock content).'
    category_key = 'files'
    icon = 'bi-file-earmark-text'
    input_schema = {
        'type': 'object',
        'properties': {'path': {'type': 'string'}},
        'required': ['path'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        path = arguments.get('path', '')
        return {
            'success': True,
            'mock': True,
            'data': {
                'path': path,
                'content': f'Mock file contents for "{path}". Live filesystem access not enabled.',
                'bytes': 128,
            },
        }


class KnowledgeSearchTool(BaseTool):
    key = 'knowledge_search'
    name = 'Knowledge Search'
    description = 'Search the Enterprise Knowledge Engine (uses live RAG search when available).'
    category_key = 'knowledge'
    icon = 'bi-journal-richtext'
    input_schema = {
        'type': 'object',
        'properties': {'query': {'type': 'string'}, 'top_k': {'type': 'integer'}},
        'required': ['query'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = arguments.get('query', '')
        top_k = int(arguments.get('top_k') or 5)
        context = context or {}
        try:
            from app.services.knowledge.search import KnowledgeSearchService
            from app.services.knowledge.types import SearchFilters
            hits = KnowledgeSearchService().search(
                query,
                top_k=top_k,
                search_type='hybrid',
                filters=SearchFilters(
                    organization_id=context.get('organization_id'),
                    user_id=context.get('user_id'),
                    project_id=context.get('project_id'),
                    campaign_id=context.get('campaign_id'),
                ),
                user_id=context.get('user_id'),
                organization_id=context.get('organization_id'),
                log=False,
            )
            return {
                'success': True,
                'mock': False,
                'data': {
                    'query': query,
                    'results': [h.to_dict() for h in hits],
                    'count': len(hits),
                },
            }
        except Exception as exc:
            return {
                'success': True,
                'mock': True,
                'data': {
                    'query': query,
                    'results': [{
                        'content': f'Mock knowledge hit for "{query}" (engine unavailable: {exc})',
                        'score': 0.5,
                    }],
                    'count': 1,
                },
            }


class WorkspaceSearchTool(BaseTool):
    key = 'workspace_search'
    name = 'Workspace Search'
    description = 'Search clients/campaigns in the workspace (stub/demo).'
    category_key = 'workspace'
    icon = 'bi-briefcase'
    input_schema = {
        'type': 'object',
        'properties': {'query': {'type': 'string'}},
        'required': ['query'],
    }

    def execute(self, arguments: Dict[str, Any], *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = arguments.get('query', '')
        context = context or {}
        user_id = context.get('user_id')
        clients, campaigns = [], []
        try:
            from app.models import Project, Campaign
            if user_id:
                clients = [
                    {'id': p.id, 'name': p.name, 'type': 'client'}
                    for p in Project.query.filter(
                        Project.user_id == user_id,
                        Project.name.ilike(f'%{query}%'),
                    ).limit(5).all()
                ]
                campaigns = [
                    {'id': c.id, 'name': c.name, 'type': 'campaign'}
                    for c in Campaign.query.filter(Campaign.name.ilike(f'%{query}%')).limit(5).all()
                ]
        except Exception:
            pass
        if not clients and not campaigns:
            return {
                'success': True,
                'mock': True,
                'data': {
                    'query': query,
                    'results': [
                        {'name': f'Mock Client matching "{query}"', 'type': 'client'},
                        {'name': f'Mock Campaign matching "{query}"', 'type': 'campaign'},
                    ],
                },
            }
        return {
            'success': True,
            'mock': False,
            'data': {'query': query, 'results': clients + campaigns},
        }


BUILTIN_TOOLS: List[BaseTool] = [
    GoogleSearchTool(),
    WebBrowserTool(),
    HttpRequestTool(),
    CalculatorTool(),
    DateTimeTool(),
    FileReaderTool(),
    KnowledgeSearchTool(),
    WorkspaceSearchTool(),
]


def get_builtin_tools() -> List[BaseTool]:
    return list(BUILTIN_TOOLS)
