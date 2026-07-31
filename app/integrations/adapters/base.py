"""Read-only adapter interface for marketing platform integrations."""


class ReadOnlyAdapter:
    """Base class for read-only platform adapters. Write operations are forbidden."""

    provider = None

    def fetch_metrics(self, connection):
        """Return list of dicts: metric_key, period_start, period_end, value."""
        raise NotImplementedError

    def fetch_importable_campaigns(self, connection):
        """Return list of dicts: external_campaign_id, external_campaign_name, external_metadata."""
        raise NotImplementedError

    def refresh_access_token(self, connection):
        """Refresh OAuth token if supported. Returns True if refreshed."""
        return False
