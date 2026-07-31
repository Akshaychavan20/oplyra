from datetime import datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app import db
from app.integrations.account_discovery import (
    build_connection_from_selection,
    list_provider_options,
    mock_provider_options,
)
from app.integrations.campaign_import import import_external_campaign
from app.integrations.oauth import (
    PROVIDER_SCOPES,
    exchange_code_for_tokens,
    integrations_mock_mode,
    start_google_oauth,
)
from app.integrations.property_selection import (
    clear_pending_oauth,
    get_pending_oauth,
    stash_pending_oauth,
)
from app.integrations.sync_engine import SyncEngine
from app.models import ExternalCampaignMap, PlatformConnection, Project

integrations_bp = Blueprint('integrations', __name__)

PROVIDER_LABELS = {
    'gsc': 'Google Search Console',
    'ga4': 'Google Analytics 4',
}

PROVIDER_DESCRIPTIONS = {
    'gsc': 'Read-only SEO performance: clicks, impressions, queries.',
    'ga4': 'Read-only analytics: sessions, users, campaigns.',
}


def _connection_dict(conn):
    importables = ExternalCampaignMap.query.filter_by(connection_id=conn.id).all()
    return {
        'id': conn.id,
        'provider': conn.provider,
        'provider_label': PROVIDER_LABELS.get(conn.provider, conn.provider),
        'status': conn.status,
        'external_account_id': conn.external_account_id,
        'external_account_name': conn.external_account_name,
        'is_mock': conn.is_mock,
        'last_sync_at': conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        'last_sync_status': conn.last_sync_status,
        'last_sync_error': conn.last_sync_error,
        'project_id': conn.project_id,
        'importable_count': len(importables),
        'importables': [
            {
                'external_campaign_id': m.external_campaign_id,
                'external_campaign_name': m.external_campaign_name,
                'campaign_id': m.campaign_id,
                'imported': bool(m.campaign_id),
            }
            for m in importables
        ],
    }


def _finalize_connection(user_id, provider, project_id, access_token, refresh_token, expires_in,
                         selected_option, all_options, is_mock=False, existing_connection_id=None):
    """Create or update a PlatformConnection from a user-selected property."""
    built = build_connection_from_selection(provider, selected_option, all_options)

    if existing_connection_id:
        conn = PlatformConnection.query.filter_by(id=existing_connection_id, user_id=user_id).first()
        if not conn:
            raise ValueError('Connection not found')
    else:
        conn = PlatformConnection.query.filter_by(
            user_id=user_id,
            provider=provider,
            external_account_id=built['external_account_id'],
        ).first()

    if not conn:
        conn = PlatformConnection(
            user_id=user_id,
            project_id=project_id,
            provider=provider,
            external_account_id=built['external_account_id'],
            external_account_name=built['external_account_name'],
            scopes=PROVIDER_SCOPES[provider],
            is_mock=is_mock,
            connection_metadata=built['connection_metadata'],
        )
        db.session.add(conn)
    else:
        conn.external_account_id = built['external_account_id']
        conn.external_account_name = built['external_account_name']
        conn.connection_metadata = built['connection_metadata']
        conn.is_mock = is_mock
        conn.project_id = project_id or conn.project_id

    conn.access_token = access_token
    if refresh_token:
        conn.refresh_token = refresh_token
    conn.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    conn.status = 'connected'
    conn.last_sync_error = None
    conn.last_sync_status = None
    db.session.commit()
    return conn


@integrations_bp.route('/', methods=['GET'])
@login_required
def connected_apps():
    """Connected Apps hub — OAuth status, manual sync, campaign import."""
    connections = PlatformConnection.query.filter_by(user_id=current_user.id).order_by(
        PlatformConnection.provider.asc()
    ).all()
    projects = Project.query.filter_by(user_id=current_user.id, is_archived=False).order_by(
        Project.name.asc()
    ).all()
    mock_mode = integrations_mock_mode()
    return render_template(
        'integrations/connected_apps.html',
        connections=connections,
        connection_payload=[_connection_dict(c) for c in connections],
        projects=projects,
        provider_labels=PROVIDER_LABELS,
        provider_descriptions=PROVIDER_DESCRIPTIONS,
        mock_mode=mock_mode,
        supported_providers=['gsc', 'ga4'],
    )


@integrations_bp.route('/api/status', methods=['GET'])
@login_required
def api_status():
    connections = PlatformConnection.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        'success': True,
        'mock_mode': integrations_mock_mode(),
        'connections': [_connection_dict(c) for c in connections],
    })


@integrations_bp.route('/connect/<provider>', methods=['GET'])
@login_required
def connect_provider(provider):
    if provider not in ('gsc', 'ga4'):
        flash('Unsupported integration provider.', 'danger')
        return redirect(url_for('integrations.connected_apps'))

    project_id = request.args.get('project_id', type=int)

    if integrations_mock_mode():
        return _start_mock_property_selection(provider, project_id)

    try:
        auth_url = start_google_oauth(provider, current_user.id, project_id)
        return redirect(auth_url)
    except Exception as exc:
        flash(f'Could not start OAuth: {exc}', 'danger')
        return redirect(url_for('integrations.connected_apps'))


def _start_mock_property_selection(provider, project_id=None):
    """Mock OAuth — show property selector with fixture options."""
    if project_id:
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()
        if not project:
            project_id = None

    options = mock_provider_options(provider)
    stash_pending_oauth(
        provider=provider,
        user_id=current_user.id,
        project_id=project_id,
        access_token='mock-access-token',
        refresh_token='mock-refresh-token',
        expires_in=86400 * 30,
        options=options,
        is_mock=True,
    )
    return redirect(url_for('integrations.select_property'))


@integrations_bp.route('/callback/google', methods=['GET'])
@login_required
def google_callback():
    stored = session.pop('integration_oauth_state', None)
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        flash(f'Google authorization denied: {error}', 'danger')
        return redirect(url_for('integrations.connected_apps'))

    if not stored or stored.get('state') != state or stored.get('user_id') != current_user.id:
        flash('Invalid OAuth state. Please try connecting again.', 'danger')
        return redirect(url_for('integrations.connected_apps'))

    provider = stored['provider']
    project_id = stored.get('project_id')

    try:
        token_data = exchange_code_for_tokens(code)
    except Exception as exc:
        flash(f'Token exchange failed: {exc}', 'danger')
        return redirect(url_for('integrations.connected_apps'))

    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 3600)

    try:
        options = list_provider_options(provider, access_token)
    except Exception as exc:
        flash(f'Connected to Google but could not list properties: {exc}', 'danger')
        return redirect(url_for('integrations.connected_apps'))

    if not options:
        flash(
            f'Google account authorized, but no {PROVIDER_LABELS[provider]} properties were found.',
            'warning',
        )
        return redirect(url_for('integrations.connected_apps'))

    stash_pending_oauth(
        provider=provider,
        user_id=current_user.id,
        project_id=project_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        options=options,
        is_mock=False,
    )
    return redirect(url_for('integrations.select_property'))


@integrations_bp.route('/select-property', methods=['GET', 'POST'])
@login_required
def select_property():
    """Property selector shown after OAuth (or when changing default property)."""
    connection_id = request.args.get('connection_id', type=int) or request.form.get('connection_id', type=int)
    pending = None
    options = []
    provider = None
    is_mock = False
    project_id = None

    if connection_id:
        conn = PlatformConnection.query.filter_by(id=connection_id, user_id=current_user.id).first_or_404()
        if conn.status == 'disconnected':
            flash('Reconnect the integration before changing its property.', 'warning')
            return redirect(url_for('integrations.connected_apps'))
        provider = conn.provider
        is_mock = conn.is_mock
        project_id = conn.project_id
        try:
            if conn.is_mock or integrations_mock_mode():
                options = mock_provider_options(provider)
            else:
                options = list_provider_options(provider, conn.access_token)
        except Exception as exc:
            flash(f'Could not load properties: {exc}', 'danger')
            return redirect(url_for('integrations.connected_apps'))
    else:
        pending = get_pending_oauth(current_user.id)
        if not pending:
            flash('Property selection expired. Please connect again.', 'warning')
            return redirect(url_for('integrations.connected_apps'))
        provider = pending['provider']
        options = pending['options']
        is_mock = pending.get('is_mock', False)
        project_id = pending.get('project_id')

    if request.method == 'POST':
        selected_id = request.form.get('property_id', '').strip()
        if not selected_id:
            flash('Please select a property.', 'danger')
            return render_template(
                'integrations/select_property.html',
                provider=provider,
                provider_label=PROVIDER_LABELS[provider],
                options=options,
                connection_id=connection_id,
                is_mock=is_mock,
            )

        selected = next((o for o in options if o['id'] == selected_id), None)
        if not selected:
            flash('Invalid property selection.', 'danger')
            return redirect(url_for('integrations.select_property', connection_id=connection_id))

        try:
            if connection_id:
                conn = PlatformConnection.query.get(connection_id)
                _finalize_connection(
                    current_user.id,
                    provider,
                    project_id,
                    conn.access_token,
                    conn.refresh_token,
                    max(int((conn.token_expires_at - datetime.utcnow()).total_seconds()), 3600) if conn.token_expires_at else 3600,
                    selected,
                    options,
                    is_mock=conn.is_mock,
                    existing_connection_id=connection_id,
                )
                flash(f'{PROVIDER_LABELS[provider]} default property updated.', 'success')
            else:
                pending = get_pending_oauth(current_user.id)
                if not pending:
                    flash('Property selection expired. Please connect again.', 'warning')
                    return redirect(url_for('integrations.connected_apps'))
                _finalize_connection(
                    current_user.id,
                    provider,
                    pending.get('project_id'),
                    pending['access_token'],
                    pending.get('refresh_token'),
                    pending.get('expires_in', 3600),
                    selected,
                    options,
                    is_mock=pending.get('is_mock', False),
                )
                clear_pending_oauth()
                flash(f'{PROVIDER_LABELS[provider]} connected successfully.', 'success')
        except Exception as exc:
            flash(f'Could not save property: {exc}', 'danger')
            return redirect(url_for('integrations.connected_apps'))

        return redirect(url_for('integrations.connected_apps'))

    return render_template(
        'integrations/select_property.html',
        provider=provider,
        provider_label=PROVIDER_LABELS[provider],
        options=options,
        connection_id=connection_id,
        is_mock=is_mock,
    )


@integrations_bp.route('/disconnect/<int:connection_id>', methods=['POST'])
@login_required
def disconnect(connection_id):
    conn = PlatformConnection.query.filter_by(id=connection_id, user_id=current_user.id).first_or_404()
    conn.status = 'disconnected'
    conn.access_token = ''
    conn.refresh_token = ''
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'connection': _connection_dict(conn)})
    flash('Integration disconnected.', 'info')
    return redirect(url_for('integrations.connected_apps'))


@integrations_bp.route('/sync/<int:connection_id>', methods=['POST'])
@login_required
def sync_now(connection_id):
    conn = PlatformConnection.query.filter_by(id=connection_id, user_id=current_user.id).first_or_404()
    try:
        sync_run = SyncEngine.run_sync(conn.id, current_user.id)
        conn = PlatformConnection.query.get(connection_id)
        payload = {
            'success': True,
            'records_read': sync_run.records_read,
            'connection': _connection_dict(conn),
        }
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify(payload)
        flash(f'Sync complete — {sync_run.records_read} records read.', 'success')
    except Exception as exc:
        conn = PlatformConnection.query.get(connection_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': str(exc), 'connection': _connection_dict(conn) if conn else None}), 400
        flash(f'Sync failed: {exc}', 'danger')
    return redirect(url_for('integrations.connected_apps'))


@integrations_bp.route('/import', methods=['POST'])
@login_required
def import_campaign():
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        connection_id = int(data.get('connection_id'))
        project_id = int(data.get('project_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'connection_id and project_id must be integers'}), 400

    external_campaign_id = data.get('external_campaign_id')
    if not external_campaign_id:
        return jsonify({'success': False, 'error': 'external_campaign_id is required'}), 400

    try:
        campaign, created = import_external_campaign(
            current_user.id, connection_id, external_campaign_id, project_id
        )
        return jsonify({
            'success': True,
            'created': created,
            'campaign': {'id': campaign.id, 'name': campaign.name, 'project_id': campaign.project_id},
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
