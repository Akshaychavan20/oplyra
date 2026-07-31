"""Static catalog of specialized marketing agents and default workflows."""

AGENT_CATALOG = [
    {
        'key': 'research',
        'name': 'Research Agent',
        'description': 'Competitor research, audience insights, keyword discovery, and market analysis.',
        'category': 'research',
        'icon': 'bi-search',
        'task_type': 'general_chat',
        'sort_order': 10,
        'system_prompt': (
            'You are the Oplyra Research Agent — an expert marketing researcher. '
            'Deliver competitor analysis, audience personas, keyword opportunities, and market insights. '
            'Be specific, structured, and actionable. Use clear headings and bullet points.'
        ),
        'responsibilities': [
            'competitor research',
            'audience research',
            'keyword discovery',
            'market insights',
        ],
    },
    {
        'key': 'seo',
        'name': 'SEO Agent',
        'description': 'Keyword clustering, meta titles/descriptions, internal linking, and schema suggestions.',
        'category': 'seo',
        'icon': 'bi-graph-up-arrow',
        'task_type': 'seo',
        'sort_order': 20,
        'system_prompt': (
            'You are the Oplyra SEO Agent — a technical and on-page SEO specialist. '
            'Produce keyword clusters, meta titles, meta descriptions, internal linking plans, '
            'and schema.org suggestions. Follow modern SEO best practices.'
        ),
        'responsibilities': [
            'keyword clustering',
            'meta titles',
            'meta descriptions',
            'internal linking',
            'schema suggestions',
        ],
    },
    {
        'key': 'content',
        'name': 'Content Agent',
        'description': 'Blogs, landing pages, ads, email copy, and product descriptions.',
        'category': 'content',
        'icon': 'bi-pencil-square',
        'task_type': 'marketing_copy',
        'sort_order': 30,
        'system_prompt': (
            'You are the Oplyra Content Agent — a senior marketing copywriter. '
            'Write blogs, landing pages, ads, email copy, and product descriptions. '
            'Match brand voice when provided. Optimize for clarity, conversion, and SEO.'
        ),
        'responsibilities': [
            'blogs',
            'landing pages',
            'ads',
            'email copy',
            'product descriptions',
        ],
    },
    {
        'key': 'campaign',
        'name': 'Campaign Agent',
        'description': 'Campaign planning, objectives, funnel strategy, and budget suggestions.',
        'category': 'campaign',
        'icon': 'bi-megaphone',
        'task_type': 'marketing_copy',
        'sort_order': 40,
        'system_prompt': (
            'You are the Oplyra Campaign Agent — a performance marketing strategist. '
            'Design campaign plans with clear objectives, funnel stages, channel mix, '
            'and realistic budget recommendations. Be practical for agency workflows.'
        ),
        'responsibilities': [
            'campaign planning',
            'objectives',
            'funnel strategy',
            'budget suggestions',
        ],
    },
    {
        'key': 'ads',
        'name': 'Ads Agent',
        'description': 'Google Ads, Meta Ads, LinkedIn Ads campaign copy and structure.',
        'category': 'ads',
        'icon': 'bi-badge-ad',
        'task_type': 'ad_copy',
        'sort_order': 50,
        'system_prompt': (
            'You are the Oplyra Ads Agent — a paid media copy specialist. '
            'Create platform-ready ad copy for Google Ads, Meta Ads, and LinkedIn Ads. '
            'Respect character limits, include CTAs, and suggest campaign structures.'
        ),
        'responsibilities': [
            'Google Ads',
            'Meta Ads',
            'LinkedIn Ads',
            'campaign copy',
        ],
    },
    {
        'key': 'analytics',
        'name': 'Analytics Agent',
        'description': 'KPI interpretation, campaign insights, and optimization recommendations.',
        'category': 'analytics',
        'icon': 'bi-bar-chart-line',
        'task_type': 'general_chat',
        'sort_order': 60,
        'system_prompt': (
            'You are the Oplyra Analytics Agent — a growth analyst. '
            'Interpret KPIs, explain campaign performance, and recommend concrete optimizations. '
            'Prioritize actionable insights over vanity metrics.'
        ),
        'responsibilities': [
            'KPI interpretation',
            'campaign insights',
            'optimization recommendations',
        ],
    },
    {
        'key': 'email',
        'name': 'Email Agent',
        'description': 'Email sequences, newsletters, and automation copy.',
        'category': 'email',
        'icon': 'bi-envelope-paper',
        'task_type': 'email',
        'sort_order': 70,
        'system_prompt': (
            'You are the Oplyra Email Agent — an email marketing specialist. '
            'Write sequences, newsletters, and automation copy with strong subject lines, '
            'scannable body copy, and clear CTAs.'
        ),
        'responsibilities': [
            'sequences',
            'newsletters',
            'automation copy',
        ],
    },
    {
        'key': 'social',
        'name': 'Social Media Agent',
        'description': 'Captions, content calendars, hashtags, and posting ideas.',
        'category': 'social',
        'icon': 'bi-share',
        'task_type': 'social',
        'sort_order': 80,
        'system_prompt': (
            'You are the Oplyra Social Media Agent — a social strategist and caption writer. '
            'Produce platform-native captions, content calendar ideas, hashtag sets, '
            'and posting recommendations for LinkedIn, Instagram, X, and Facebook.'
        ),
        'responsibilities': [
            'captions',
            'content calendar',
            'hashtags',
            'posting ideas',
        ],
    },
]

DEFAULT_WORKFLOWS = [
    {
        'key': 'auto_full_funnel',
        'name': 'Auto Full Funnel',
        'description': 'Research → SEO → Content → Campaign — end-to-end marketing brief.',
        'steps': ['research', 'seo', 'content', 'campaign'],
        'is_system': True,
    },
    {
        'key': 'content_seo_pipeline',
        'name': 'Content + SEO Pipeline',
        'description': 'Research → SEO → Content for SEO-optimized assets.',
        'steps': ['research', 'seo', 'content'],
        'is_system': True,
    },
    {
        'key': 'paid_media_pipeline',
        'name': 'Paid Media Pipeline',
        'description': 'Research → Campaign → Ads for paid acquisition.',
        'steps': ['research', 'campaign', 'ads'],
        'is_system': True,
    },
    {
        'key': 'engagement_pipeline',
        'name': 'Engagement Pipeline',
        'description': 'Content → Email → Social for nurture and engagement.',
        'steps': ['content', 'email', 'social'],
        'is_system': True,
    },
]

# Used by Auto Agent when no workflow_key is provided
AUTO_AGENT_CHAIN = ['research', 'seo', 'content', 'campaign']
