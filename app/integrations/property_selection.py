"""Session helpers for pending OAuth property selection."""
from datetime import datetime, timedelta

from flask import session

PENDING_SESSION_KEY = 'integration_pending'
PENDING_TTL_MINUTES = 15


def stash_pending_oauth(provider, user_id, project_id, access_token, refresh_token, expires_in, options, is_mock=False):
    session[PENDING_SESSION_KEY] = {
        'provider': provider,
        'user_id': user_id,
        'project_id': project_id,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': expires_in,
        'options': options,
        'is_mock': is_mock,
        'created_at': datetime.utcnow().isoformat(),
    }


def get_pending_oauth(user_id):
    pending = session.get(PENDING_SESSION_KEY)
    if not pending or pending.get('user_id') != user_id:
        return None
    created = datetime.fromisoformat(pending['created_at'])
    if datetime.utcnow() - created > timedelta(minutes=PENDING_TTL_MINUTES):
        clear_pending_oauth()
        return None
    return pending


def clear_pending_oauth():
    session.pop(PENDING_SESSION_KEY, None)
