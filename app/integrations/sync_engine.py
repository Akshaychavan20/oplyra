"""Manual read-only sync orchestrator."""
from datetime import datetime

from app import db
from app.integrations.adapters import get_adapter
from app.models import ExternalCampaignMap, PlatformConnection, SyncRun, SyncedMetric


class SyncEngine:
    """Runs a single read-only sync for one platform connection."""

    @staticmethod
    def run_sync(connection_id, user_id):
        connection = PlatformConnection.query.filter_by(id=connection_id, user_id=user_id).first()
        if not connection:
            raise ValueError('Connection not found')
        if connection.status == 'disconnected':
            raise ValueError('Connection is disconnected')

        sync_run = SyncRun(connection_id=connection.id, status='running', records_read=0)
        db.session.add(sync_run)
        db.session.commit()

        records = 0
        try:
            adapter = get_adapter(connection.provider)
            adapter.refresh_access_token(connection)

            metrics = adapter.fetch_metrics(connection)
            for m in metrics:
                SyncEngine._upsert_metric(connection, m)
                records += 1

            campaigns = adapter.fetch_importable_campaigns(connection)
            for c in campaigns:
                SyncEngine._upsert_external_campaign(connection, c)
                records += 1

            connection.last_sync_at = datetime.utcnow()
            connection.last_sync_status = 'success'
            connection.last_sync_error = None
            connection.status = 'connected'

            sync_run.status = 'success'
            sync_run.records_read = records
            sync_run.finished_at = datetime.utcnow()
            db.session.commit()
            return sync_run

        except Exception as exc:
            db.session.rollback()
            sync_run = SyncRun.query.get(sync_run.id)
            connection = PlatformConnection.query.get(connection_id)
            if sync_run:
                sync_run.status = 'error'
                sync_run.error_message = str(exc)[:500]
                sync_run.finished_at = datetime.utcnow()
            if connection:
                connection.last_sync_status = 'error'
                connection.last_sync_error = str(exc)[:500]
                connection.status = 'error'
            db.session.commit()
            raise

    @staticmethod
    def _upsert_metric(connection, metric):
        existing = SyncedMetric.query.filter_by(
            connection_id=connection.id,
            metric_key=metric['metric_key'],
            period_start=metric['period_start'],
            period_end=metric['period_end'],
        ).first()
        if existing:
            existing.value = metric['value']
            existing.project_id = connection.project_id
            existing.synced_at = datetime.utcnow()
        else:
            row = SyncedMetric(
                connection_id=connection.id,
                project_id=connection.project_id,
                metric_key=metric['metric_key'],
                period_start=metric['period_start'],
                period_end=metric['period_end'],
            )
            row.value = metric['value']
            db.session.add(row)

    @staticmethod
    def _upsert_external_campaign(connection, item):
        existing = ExternalCampaignMap.query.filter_by(
            connection_id=connection.id,
            external_campaign_id=item['external_campaign_id'],
        ).first()
        now = datetime.utcnow()
        if existing:
            existing.external_campaign_name = item['external_campaign_name']
            existing.external_metadata = item.get('external_metadata', {})
            existing.last_seen_at = now
            if connection.project_id and not existing.project_id:
                existing.project_id = connection.project_id
        else:
            db.session.add(ExternalCampaignMap(
                connection_id=connection.id,
                external_campaign_id=item['external_campaign_id'],
                external_campaign_name=item['external_campaign_name'],
                project_id=connection.project_id,
                external_metadata=item.get('external_metadata', {}),
                last_seen_at=now,
            ))
