from app.integrations.adapters.google_analytics4 import GoogleAnalytics4Adapter
from app.integrations.adapters.google_search_console import GoogleSearchConsoleAdapter

ADAPTERS = {
    'gsc': GoogleSearchConsoleAdapter,
    'ga4': GoogleAnalytics4Adapter,
}


def get_adapter(provider):
    cls = ADAPTERS.get(provider)
    if not cls:
        raise ValueError(f'Unsupported provider: {provider}')
    return cls()
