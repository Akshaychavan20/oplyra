"""Manual campaign import from synced external campaigns."""
from datetime import datetime

from app import db
from app.models import (
    Campaign,
    CampaignLifecycleItem,
    ExternalCampaignMap,
    Membership,
    Organization,
    PlatformConnection,
    Project,
)

IMPORT_CHECKLIST = {
    'Onboarding': ['Review imported campaign data'],
    'Monitoring': ['Verify synced metrics match platform'],
    'Reporting': ['Prepare client performance report'],
}

PROVIDER_CAMPAIGN_TYPES = {
    'gsc': 'seo',
    'ga4': 'social_campaign',
}


def import_external_campaign(user_id, connection_id, external_campaign_id, project_id):
    """Import one external campaign into Client → Campaign. Idempotent."""
    connection = PlatformConnection.query.filter_by(id=connection_id, user_id=user_id).first()
    if not connection:
        raise ValueError('Connection not found')

    project = Project.query.filter_by(id=project_id, user_id=user_id).first()
    if not project:
        raise ValueError('Client not found')

    ext_map = ExternalCampaignMap.query.filter_by(
        connection_id=connection_id,
        external_campaign_id=external_campaign_id,
    ).first()
    if not ext_map:
        raise ValueError('External campaign not found. Run Sync first.')

    if ext_map.campaign_id:
        campaign = Campaign.query.get(ext_map.campaign_id)
        return campaign, False

    membership = Membership.query.filter_by(user_id=user_id).first()
    if not membership:
        # Defensive fallback: provision a default organization for legacy users
        # created before registration auto-provisioning existed.
        org = Organization(name=f'{project.owner.username}\'s Workspace', plan_tier='pro')
        db.session.add(org)
        db.session.commit()
        membership = Membership(organization_id=org.id, user_id=user_id, role='admin')
        db.session.add(membership)
        db.session.commit()

    campaign = Campaign(
        organization_id=membership.organization_id,
        project_id=project_id,
        name=ext_map.external_campaign_name,
        type=PROVIDER_CAMPAIGN_TYPES.get(connection.provider, 'social_campaign'),
        description=f'Imported from {connection.provider.upper()} ({connection.external_account_name}). Read-only sync.',
        status='active',
        current_stage='Monitoring',
    )
    db.session.add(campaign)
    db.session.flush()

    for stage, items in IMPORT_CHECKLIST.items():
        for item_name in items:
            db.session.add(CampaignLifecycleItem(
                campaign_id=campaign.id,
                stage=stage,
                name=item_name,
                is_completed=False,
            ))

    ext_map.campaign_id = campaign.id
    ext_map.project_id = project_id
    ext_map.imported_at = datetime.utcnow()
    db.session.commit()
    return campaign, True
