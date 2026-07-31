"""Deterministic mock payloads for integration adapters when OAuth is unavailable."""
from datetime import date, timedelta


def gsc_metrics(site_url='https://example.com'):
    end = date.today()
    start = end - timedelta(days=28)
    return [
        {
            'metric_key': 'gsc.summary',
            'period_start': start,
            'period_end': end,
            'value': {
                'site_url': site_url,
                'clicks': 1240,
                'impressions': 48200,
                'ctr': 2.57,
                'position': 14.3,
            },
        },
        {
            'metric_key': 'gsc.top_queries',
            'period_start': start,
            'period_end': end,
            'value': {
                'queries': [
                    {'query': 'best widgets', 'clicks': 120, 'impressions': 3400},
                    {'query': 'widget reviews', 'clicks': 85, 'impressions': 2100},
                ],
            },
        },
    ]


def gsc_importable(site_url='https://example.com'):
    return [
        {
            'external_campaign_id': f'gsc-site:{site_url}',
            'external_campaign_name': f'SEO Property — {site_url}',
            'external_metadata': {'site_url': site_url, 'source': 'gsc'},
        },
    ]


def ga4_metrics(property_id='properties/123456789'):
    end = date.today()
    start = end - timedelta(days=28)
    return [
        {
            'metric_key': 'ga4.summary',
            'period_start': start,
            'period_end': end,
            'value': {
                'property_id': property_id,
                'sessions': 8420,
                'users': 6150,
                'bounce_rate': 42.1,
                'avg_session_duration': 142,
            },
        },
    ]


def ga4_importable(property_id='properties/123456789'):
    return [
        {
            'external_campaign_id': 'ga4-campaign:summer_promo_2026',
            'external_campaign_name': 'Summer Promo 2026',
            'external_metadata': {'property_id': property_id, 'source': 'ga4', 'medium': 'cpc'},
        },
        {
            'external_campaign_id': 'ga4-campaign:brand_awareness_q2',
            'external_campaign_name': 'Brand Awareness Q2',
            'external_metadata': {'property_id': property_id, 'source': 'ga4', 'medium': 'organic'},
        },
    ]
