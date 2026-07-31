"""Post-OAuth property listing for GSC and GA4 (no auto-selection)."""
import requests

GSC_SITES_URL = 'https://www.googleapis.com/webmasters/v3/sites'
GA4_ACCOUNT_SUMMARIES_URL = 'https://analyticsadmin.googleapis.com/v1beta/accountSummaries'

MOCK_GSC_OPTIONS = [
    {'id': 'https://example.com', 'label': 'https://example.com (Mock Site A)', 'site_url': 'https://example.com'},
    {'id': 'https://demo-client.com', 'label': 'https://demo-client.com (Mock Site B)', 'site_url': 'https://demo-client.com'},
]

MOCK_GA4_OPTIONS = [
    {'id': 'properties/123456789', 'label': 'Mock GA4 Property A (properties/123456789)', 'property_id': 'properties/123456789', 'display_name': 'Mock GA4 Property A'},
    {'id': 'properties/987654321', 'label': 'Mock GA4 Property B (properties/987654321)', 'property_id': 'properties/987654321', 'display_name': 'Mock GA4 Property B'},
]


def format_http_error(resp):
    """Extract a readable message from a Google API error response."""
    try:
        payload = resp.json()
        err = payload.get('error', {})
        message = err.get('message') or resp.text
        status = err.get('status') or resp.reason
        return f'{status}: {message}'
    except Exception:
        return f'HTTP {resp.status_code}: {resp.text[:200]}'


def list_gsc_sites(access_token):
    """Return selectable GSC site options (read-only list)."""
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = requests.get(GSC_SITES_URL, headers=headers, timeout=30)
    if not resp.ok:
        raise ValueError(format_http_error(resp))

    options = []
    for entry in resp.json().get('siteEntry', []):
        site_url = entry.get('siteUrl', '')
        if not site_url:
            continue
        permission = entry.get('permissionLevel', '')
        label = site_url
        if permission:
            label = f'{site_url} ({permission})'
        options.append({
            'id': site_url,
            'label': label,
            'site_url': site_url,
            'permission': permission,
        })
    return options


def list_ga4_properties(access_token):
    """Return selectable GA4 property options (read-only list)."""
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = requests.get(GA4_ACCOUNT_SUMMARIES_URL, headers=headers, timeout=30)
    if not resp.ok:
        raise ValueError(format_http_error(resp))

    options = []
    for account in resp.json().get('accountSummaries', []):
        account_name = account.get('displayName', '')
        for prop in account.get('propertySummaries', []):
            prop_id = prop.get('property', '')
            prop_name = prop.get('displayName', prop_id)
            if not prop_id:
                continue
            label = f'{prop_name} ({prop_id})'
            if account_name:
                label = f'{prop_name} — {account_name} ({prop_id})'
            options.append({
                'id': prop_id,
                'label': label,
                'property_id': prop_id,
                'display_name': prop_name,
                'account_name': account_name,
            })
    return options


def list_provider_options(provider, access_token):
    if provider == 'gsc':
        return list_gsc_sites(access_token)
    if provider == 'ga4':
        return list_ga4_properties(access_token)
    raise ValueError(f'Unsupported provider: {provider}')


def mock_provider_options(provider):
    if provider == 'gsc':
        return list(MOCK_GSC_OPTIONS)
    if provider == 'ga4':
        return list(MOCK_GA4_OPTIONS)
    raise ValueError(f'Unsupported provider: {provider}')


def build_connection_from_selection(provider, option, all_options):
    """Build PlatformConnection fields from a user-selected property."""
    if provider == 'gsc':
        site_url = option['site_url']
        all_sites = [o['site_url'] for o in all_options]
        return {
            'external_account_id': f'gsc-site:{site_url}',
            'external_account_name': f'SEO Property — {site_url}',
            'connection_metadata': {'site_url': site_url, 'sites': all_sites},
        }
    if provider == 'ga4':
        prop_id = option['property_id']
        all_props = [
            {'property_id': o['property_id'], 'display_name': o.get('display_name', o['property_id'])}
            for o in all_options
        ]
        display = option.get('display_name', prop_id)
        return {
            'external_account_id': prop_id,
            'external_account_name': f'{display} ({prop_id})',
            'connection_metadata': {'property_id': prop_id, 'properties': all_props},
        }
    raise ValueError(f'Unsupported provider: {provider}')
