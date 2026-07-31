import json
from datetime import datetime, timedelta
from app import db
from app.models import Campaign, CampaignLifecycleItem, Task, Note, Report, AutomationRule, Reminder, ActivityLog, TimelineMilestone, Project

PLAYBOOKS = {
    "facebook_lead_gen": {
        "name": "Facebook Lead Generation",
        "type": "social_campaign",
        "description": "Standard high-converting Facebook lead forms setup targeting localized demographics.",
        "checklist": {
            "Onboarding": ["Define target demographics", "Setup Facebook Page permissions", "Integrate Facebook Pixel"],
            "Planning": ["Create lead magnet draft", "Confirm ad copy messaging", "Approve target audience brief"],
            "Execution": ["Upload creatives to Ads Manager", "Deploy lead form setup", "Publish initial campaigns"],
            "Monitoring": ["Monitor Cost Per Lead (CPL)", "Evaluate click-through rate (CTR)", "Optimize form fields"],
            "Reporting": ["Compile lead quality metrics", "Deliver final attribution report"]
        },
        "notes": [
            {
                "title": "Lead Magnet & Copy Brief",
                "body": "<h4>Lead Magnet Objective</h4><p>Promote high-value download or local discount offer in exchange for email/phone details.</p><h4>Copy Variations</h4><p>Copy 1 (Benefit-focused): ...<br>Copy 2 (Urgency-focused): ...</p>"
            }
        ]
    },
    "google_search": {
        "name": "Google Search Campaign",
        "type": "affiliate",
        "description": "Target intent-driven keywords with optimized Google search bidding structures.",
        "checklist": {
            "Onboarding": ["Link Google Ads to Analytics", "Verify conversion tracking tag", "Perform negative keyword seeding"],
            "Planning": ["Perform keyword research", "Define search ad copy structure", "Determine max CPC bidding"],
            "Execution": ["Configure search campaign bidding", "Create ad groups and keywords", "Launch search campaign"],
            "Monitoring": ["Evaluate search term match types", "Monitor quality scores", "Audit budget consumption"],
            "Reporting": ["Compile conversion rate reports", "Deliver cost-per-click efficiency logs"]
        },
        "notes": [
            {
                "title": "Keyword Strategy & Negatives",
                "body": "<h4>Core Keywords to Bid</h4><ul><li>Keyword 1 (High intent)</li><li>Keyword 2 (Brand intent)</li></ul><h4>Negative List</h4><p>Add negatives to prevent unwanted clicks: free, torrent, cheap, job.</p>"
            }
        ]
    },
    "seo_campaign": {
        "name": "SEO Campaign",
        "type": "seo",
        "description": "Long-term organic traffic development with structured content templates and onsite checks.",
        "checklist": {
            "Onboarding": ["Setup Google Search Console", "Install Yoast / SEO meta plugin", "Audit site schema structure"],
            "Planning": ["Identify 10 target blog keywords", "Outline semantic linking maps", "Define competitor content gaps"],
            "Execution": ["Publish first 3 blog posts", "Optimize image alt attributes", "Configure sitemap.xml indexing"],
            "Monitoring": ["Monitor keyword ranking shifts", "Check organic traffic metrics", "Verify index status in GSC"],
            "Reporting": ["Deliver organic traffic growth summary", "Report keyword ranking achievements"]
        },
        "notes": [
            {
                "title": "SEO Blog Content Outline",
                "body": "<h4>SEO Pillar Article Ideas</h4><p>Pillar 1: Complete guide to topic... (Targeting Keyword 1)</p><h4>Backlink Opportunities</h4><p>List target industry directories and local blogs for guest posting outreach.</p>"
            }
        ]
    },
    "local_business": {
        "name": "Local Business Campaign",
        "type": "social_campaign",
        "description": "Enhance localized foot traffic and awareness for local businesses via map citations and target radius ads.",
        "checklist": {
            "Onboarding": ["Verify Google Business Profile status", "Perform local citation audits", "Setup local Facebook page check-ins"],
            "Planning": ["Create review solicitation templates", "Define local target radius (e.g. 5 miles)", "Design special coupon creatives"],
            "Execution": ["Deploy location-specific target ads", "Publish review link to social profiles", "List business on top local citation sites"],
            "Monitoring": ["Evaluate direct directions clicks", "Monitor calls from map listings", "Check Facebook local engagement"],
            "Reporting": ["Summarize localized impressions", "Compile reviews obtained report"]
        },
        "notes": [
            {
                "title": "Local Review Strategy Note",
                "body": "<h4>Review Campaign Objectives</h4><p>Sollicit customers for Google Reviews using a customized short link.</p><h4>Radius Ad Parameters</h4><p>Geo Target: 5 mile radius around store coordinates.<br>Demographics: Aged 25-54.</p>"
            }
        ]
    },
    "ecommerce": {
        "name": "E-commerce Campaign",
        "type": "product_launch",
        "description": "Run conversion-optimized product catalogs, retargeting funnels, and cart recovery flows.",
        "checklist": {
            "Onboarding": ["Configure Merchant Center integration", "Sync ecommerce product catalog feed", "Setup cart abandonment track events"],
            "Planning": ["Define seasonal discount tiers", "Outline cart email sequence", "Select priority products to boost"],
            "Execution": ["Launch dynamic catalog remarketing ads", "Activate automated abandonment email flows", "Deploy search shopping ads"],
            "Monitoring": ["Evaluate Return on Ad Spend (ROAS)", "Track checkout cart drop-offs", "Analyze product performance trends"],
            "Reporting": ["Deliver total store purchase attribution", "Report average order value metrics"]
        },
        "notes": [
            {
                "title": "Retargeting Catalog Copy Draft",
                "body": "<h4>Abandonment Offer Copy</h4><p>'Still thinking about it? Here is 10% off your cart items with code SAVE10. Complete checkout today!'</p>"
            }
        ]
    },
    "restaurant": {
        "name": "Restaurant Campaign",
        "type": "social_campaign",
        "description": "Increase reservations, delivery orders, and visual menu awareness utilizing Instagram visuals and local search.",
        "checklist": {
            "Onboarding": ["Claim Yelp and TripAdvisor profile listings", "Install reservation tracking widgets", "Setup Instagram professional page"],
            "Planning": ["Schedule menu photo shoot session", "Design happy-hour coupon specials", "Define foodie audience filters"],
            "Execution": ["Publish high-quality menu reel assets", "Deploy weekend dinner target ads", "Launch geo-radius story campaigns"],
            "Monitoring": ["Track reservations clicked", "Evaluate delivery menu clicks", "Monitor food influencer outreach replies"],
            "Reporting": ["Deliver reservation conversion audit", "Report menu view engagement metrics"]
        },
        "notes": [
            {
                "title": "Restaurant Social Post Plan",
                "body": "<h4>Menu Spotlight Reel Strategy</h4><p>Record a 15-second teaser of the signature chef dish. Link directly to reservation page in bio.</p>"
            }
        ]
    },
    "clinic": {
        "name": "Clinic Campaign",
        "type": "social_campaign",
        "description": "Increase local clinic appointment bookings with HIPAA-aware client capture funnels.",
        "checklist": {
            "Onboarding": ["Confirm clinic intake booking link", "Audit HIPAA-compliance warning notices", "Review clinic listing accuracy"],
            "Planning": ["Write customer-education blog drafts", "Design safety-focused copy cards", "Approve service availability listings"],
            "Execution": ["Deploy local search appointments ads", "Setup book-now button on Facebook page", "Distribute educational clinics brief"],
            "Monitoring": ["Track appointments submitted", "Review cost-per-scheduled-booking", "Monitor patient review scores"],
            "Reporting": ["Deliver patient acquisitions brief", "Report call conversions summary"]
        },
        "notes": [
            {
                "title": "Clinic FAQ & Booking Setup",
                "body": "<h4>Common Intake Questions</h4><p>Prepare standard FAQ note to auto-respond to initial booking inquiries.</p>"
            }
        ]
    },
    "gym": {
        "name": "Gym Campaign",
        "type": "product_launch",
        "description": "Drive gym signups and trial pass redemptions via high-energy video ads and class sign-up pages.",
        "checklist": {
            "Onboarding": ["Verify gym booking software integration", "Setup free trial confirmation page", "Define membership tier links"],
            "Planning": ["Record member testimonial clips", "Outline free trial offer parameters", "Prepare gym schedule flyers"],
            "Execution": ["Launch class pass discount target ads", "Deploy gym member success reels", "Publish free guest pass forms"],
            "Monitoring": ["Monitor pass redemption rate", "Evaluate cost-per-lead for gym trials", "Audit membership checkout steps"],
            "Reporting": ["Deliver trial-to-membership conversions", "Report social engagement achievements"]
        },
        "notes": [
            {
                "title": "Gym Membership Offer Sheet",
                "body": "<h4>Core Promotion Hook</h4><p>'Get a 3-Day All-Access Pass Free! Try any classes, no contracts.'</p>"
            }
        ]
    },
    "furniture_store": {
        "name": "Furniture Store Campaign",
        "type": "product_launch",
        "description": "Showcase showrooms and high-value catalog items, driving local appointments or store check-ins.",
        "checklist": {
            "Onboarding": ["Setup local directory map citations", "Link catalog photos to social platforms", "Verify showroom booking links"],
            "Planning": ["Define financing promotion flyers", "Select high-margin items to showcase", "Confirm showroom consultation steps"],
            "Execution": ["Launch catalog showroom carousels", "Deploy zero-percent financing search ads", "Send email update to local list"],
            "Monitoring": ["Monitor design consultation signups", "Evaluate map direction click trends", "Track showroom coupon claims"],
            "Reporting": ["Deliver design booking attribution report", "Report catalog interest stats"]
        },
        "notes": [
            {
                "title": "Financing & Item Showcase List",
                "body": "<h4>Financing Details</h4><p>12 Months Interest Free on purchases over $999.</p><h4>Showcase Items</h4><p>Sectional Sofa, Dining Table Set.</p>"
            }
        ]
    }
}

class AutomationEngine:
    """Core automation manager for Playbooks, Auto-Tasks, Rules, Feed & Reminders."""

    @staticmethod
    def create_campaign_from_wizard(user_id, org_id, project_id, name, playbook_key, goal, platforms, budget, start_date, end_date, import_campaign_id=None, currency='INR', duration_type='fixed', recurrence=None):
        # 1. Instantiate campaign
        from app.utils.currency import normalize_currency

        playbook = PLAYBOOKS.get(playbook_key)
        type_val = playbook["type"] if playbook else "social_campaign"
        desc_val = f"Playbook: {playbook['name'] if playbook else playbook_key}. Goal: {goal}. Platforms: {', '.join(platforms)}."

        allowed_durations = {'fixed', 'ongoing', 'recurring'}
        duration_type = (duration_type or 'fixed').strip().lower()
        if duration_type not in allowed_durations:
            duration_type = 'fixed'

        allowed_recurrence = {'daily', 'weekly', 'monthly', 'quarterly', 'yearly'}
        recurrence_val = None
        if duration_type == 'recurring':
            recurrence_val = (recurrence or 'weekly').strip().lower()
            if recurrence_val not in allowed_recurrence:
                recurrence_val = 'weekly'
        # Ongoing / evergreen never stores an end date
        if duration_type == 'ongoing':
            end_date = None
        
        campaign = Campaign(
            organization_id=org_id,
            project_id=project_id,
            name=name,
            type=type_val,
            description=desc_val,
            budget=budget,
            currency=normalize_currency(currency),
            start_date=start_date,
            end_date=end_date,
            duration_type=duration_type,
            recurrence=recurrence_val,
            status="active",
            current_stage="Onboarding"
        )
        db.session.add(campaign)
        db.session.commit()

        # 2. Seed Campaign Checklist Items based on Playbook
        checklist_data = playbook["checklist"] if playbook else {
            "Onboarding": ["Setup campaign parameters", "Initialize platforms"],
            "Planning": ["Define objectives"],
            "Execution": ["Launch ad sets"],
            "Monitoring": ["Audit performance indicators"],
            "Reporting": ["Deliver client KPI brief"]
        }

        for stage, items in checklist_data.items():
            for item_name in items:
                db_item = CampaignLifecycleItem(
                    campaign_id=campaign.id,
                    stage=stage,
                    name=item_name,
                    is_completed=False
                )
                db.session.add(db_item)

        # 3. Seed Playbook Default Notes
        if playbook and "notes" in playbook:
            for note_tpl in playbook["notes"]:
                new_note = Note(
                    campaign_id=campaign.id,
                    project_id=project_id,
                    user_id=user_id,
                    title=note_tpl["title"],
                    body=note_tpl["body"]
                )
                db.session.add(new_note)

        # 4. Generate Initial Playbook Tasks (Onboarding tasks)
        onboarding_tasks = [
            ("Audit setup parameters", "high", "Verify campaign parameters match contract."),
            ("Configure target audience profile", "medium", f"Outline target profile based on {goal} and {playbook_key} playbooks.")
        ]
        
        # Inject platform-specific tasks
        if "facebook" in platforms:
            onboarding_tasks.append(("Verify Facebook Business Page integration", "medium", "Check page access rights."))
        if "google" in platforms:
            onboarding_tasks.append(("Link Google Ads Account", "medium", "Ensure correct client account CID linking."))
        if "seo" in platforms:
            onboarding_tasks.append(("Verify SEO site sitemap indexing", "medium", "Check search engine access path."))

        for title, prio, desc in onboarding_tasks:
            task = Task(
                campaign_id=campaign.id,
                project_id=project_id,
                user_id=user_id,
                title=title,
                priority=prio,
                description=desc,
                status="pending",
                due_date=(datetime.utcnow() + timedelta(days=2))
            )
            db.session.add(task)

        # 5. Populate Timeline Milestones (recommended dates)
        stages = ["Onboarding", "Planning", "Execution", "Monitoring", "Reporting", "Completed"]
        days_per_stage = 3
        current_time = start_date if start_date else datetime.utcnow()
        for idx, stage in enumerate(stages):
            m_due = current_time + timedelta(days=idx * days_per_stage)
            milestone = TimelineMilestone(
                campaign_id=campaign.id,
                stage=stage,
                title=f"Stage Milestone: {stage} Deliverables",
                due_date=m_due,
                status="pending"
            )
            db.session.add(milestone)

        # 6. Enable default simple rules in Automation Center
        rules = [
            ("deadline_tomorrow", "create_reminder"),
            ("stage_start_reporting", "prepare_report_draft"),
            ("campaign_completed", "suggest_archive")
        ]
        for trigger, action in rules:
            rule = AutomationRule(
                campaign_id=campaign.id,
                trigger_type=trigger,
                action_type=action,
                is_enabled=True
            )
            db.session.add(rule)

        # 7. Workflow Automation: Copy structures from existing campaign if requested
        if import_campaign_id:
            src_campaign = Campaign.query.get(import_campaign_id)
            if src_campaign:
                # Copy existing pending tasks
                for src_task in src_campaign.tasks:
                    if src_task.status != "completed" and not src_task.is_archived:
                        cloned_task = Task(
                            campaign_id=campaign.id,
                            project_id=project_id,
                            user_id=user_id,
                            title=src_task.title,
                            priority=src_task.priority,
                            description=src_task.description,
                            status="pending",
                            due_date=(datetime.utcnow() + timedelta(days=4))
                        )
                        db.session.add(cloned_task)
                # Copy existing notes
                for src_note in src_campaign.notes:
                    cloned_note = Note(
                        campaign_id=campaign.id,
                        project_id=project_id,
                        user_id=user_id,
                        title=f"[Copy] {src_note.title}",
                        body=src_note.body
                    )
                    db.session.add(cloned_note)

        # Commit all DB operations
        db.session.commit()

        # Log Activity of Creation
        AutomationEngine.log_activity(
            campaign.id, 
            user_id, 
            "campaign_updated", 
            f"Campaign initialized using '{playbook['name'] if playbook else playbook_key}' playbook."
        )

        return campaign

    @staticmethod
    def generate_stage_tasks(campaign, stage):
        """Automatically create stage-specific tasks dynamically if they don't exist."""
        task_templates = {
            "Planning": [
                ("Keyword Research Analysis", "medium", "Identify competitive phrases and search intent levels."),
                ("Audience Demographics Research", "medium", "Outline target profiles and placement vectors."),
                ("Competitor Creative Analysis", "low", "Audit active competing copywriting hooks and creatives.")
            ],
            "Execution": [
                ("Launch Live Campaigns", "high", "Deploy target bidding strategies and publishing configurations."),
                ("Upload Ad Creatives and Copy", "medium", "Publish approved copy models and visual banners."),
                ("Install & Test Tracking Pixel", "high", "Verify pixel triggers match lead conversion paths.")
            ],
            "Monitoring": [
                ("Audit CTR Performance Trends", "medium", "Review click-through counts and flag anomalies."),
                ("Review Budget Bidding Efficiency", "high", "Assess ad spends and optimize target cost limits."),
                ("Filter Search Term Logs", "low", "Flag negative terms and update block lists.")
            ],
            "Reporting": [
                ("Generate Automated Weekly Report", "high", "Compile dashboard metrics for client delivery."),
                ("Prepare Executive Brief Summary", "medium", "Draft context performance statements.")
            ]
        }

        created = []
        if stage in task_templates:
            existing_titles = [t.title for t in campaign.tasks]
            for title, priority, desc in task_templates[stage]:
                if title not in existing_titles:
                    task = Task(
                        campaign_id=campaign.id,
                        project_id=campaign.project_id,
                        user_id=campaign.project.user_id,
                        title=title,
                        priority=priority,
                        description=desc,
                        status="pending",
                        due_date=(datetime.utcnow() + timedelta(days=3))
                    )
                    db.session.add(task)
                    created.append(task)
            
            if created:
                db.session.commit()
                AutomationEngine.log_activity(
                    campaign.id,
                    campaign.project.user_id,
                    "task_completed",
                    f"Auto-generated {len(created)} tasks for '{stage}' stage."
                )
        return created

    @staticmethod
    def evaluate_rules(campaign, trigger):
        """Evaluates enabled automation rules for a campaign and executes action side-effects."""
        active_rules = AutomationRule.query.filter_by(campaign_id=campaign.id, trigger_type=trigger, is_enabled=True).all()
        for rule in active_rules:
            if rule.action_type == "create_reminder":
                # Create Smart Reminder in database
                reminder = Reminder(
                    campaign_id=campaign.id,
                    user_id=campaign.project.user_id,
                    title=f"{campaign.name} Action Alert",
                    context_text=f"A campaign milestone or task deadline is approaching tomorrow. Confirm progress today?"
                )
                db.session.add(reminder)
                db.session.commit()

            elif rule.action_type == "prepare_report_draft":
                # Check if report draft already exists
                existing = Report.query.filter_by(campaign_id=campaign.id, title="[Auto Draft] Campaign Summary Brief").first()
                if not existing:
                    # Compile auto summary content markdown
                    summary = f"# Campaign Performance Summary: {campaign.name}\n\n"
                    summary += "## Executive Summary\n"
                    summary += "We are finalizing execution stages. Overall milestone completions stand at good level.\n\n"
                    summary += "## WhatsApp Client Brief (Copy-Paste)\n"
                    summary += f"Hey! Here is the weekly update for {campaign.name}: All targets completed successfully. Budget tracking healthy. Let me know if you want to hop on a call to sync! \n\n"
                    summary += "## Email Template Draft\n"
                    summary += "Dear Client,\n\nPlease find our performance brief attached to review. Spends remain within targets.\n\nBest,\nMarketing Team"
                    
                    draft_report = Report(
                        campaign_id=campaign.id,
                        project_id=campaign.project_id,
                        user_id=campaign.project.user_id,
                        title="[Auto Draft] Campaign Summary Brief",
                        content_markdown=summary
                    )
                    db.session.add(draft_report)
                    db.session.commit()

                    # Create a Reminder alerting the user
                    rem = Reminder(
                        campaign_id=campaign.id,
                        user_id=campaign.project.user_id,
                        title="Draft Report Ready",
                        context_text=f"Reporting stage started for {campaign.name}. Performance brief draft is pre-compiled."
                    )
                    db.session.add(rem)
                    db.session.commit()

                    AutomationEngine.log_activity(
                        campaign.id,
                        campaign.project.user_id,
                        "report_generated",
                        "Smart draft performance summary prepared automatically."
                    )

            elif rule.action_type == "suggest_archive":
                # Add reminder that campaign is complete, suggest archiving
                rem = Reminder(
                    campaign_id=campaign.id,
                    user_id=campaign.project.user_id,
                    title="Suggest Campaign Archive",
                    context_text=f"Campaign '{campaign.name}' completed. All objectives achieved. Archive project settings?"
                )
                db.session.add(rem)
                db.session.commit()

    @staticmethod
    def get_reminders(user_id):
        """Fetches active user reminders, seeding dynamic warning checks if overdue."""
        # 1. Fetch DB reminders
        db_reminders = Reminder.query.filter_by(user_id=user_id, is_read=False).order_by(Reminder.created_at.desc()).all()
        reminders_list = []
        for r in db_reminders:
            reminders_list.append({
                "id": r.id,
                "campaign_name": r.campaign.name if r.campaign else "Workspace",
                "title": r.title,
                "context": r.context_text,
                "campaign_id": r.campaign_id,
                "created_at": r.created_at.strftime('%Y-%m-%d %H:%M')
            })

        # 2. Dynamic warning alerts (overdue task checks)
        active_campaigns = Campaign.query.join(Project).filter(Project.user_id == user_id, Campaign.status == 'active').all()
        for camp in active_campaigns:
            for task in camp.tasks:
                if task.status != 'completed' and not task.is_archived and task.due_date:
                    time_diff = datetime.utcnow() - task.due_date
                    if time_diff.days >= 1:
                        reminders_list.append({
                            "id": f"dynamic-overdue-{task.id}",
                            "campaign_name": camp.name,
                            "title": f"Task Overdue: {task.title}",
                            "context": f"Checklist objective is overdue by {time_diff.days} days. Review and complete now?",
                            "campaign_id": camp.id,
                            "created_at": task.due_date.strftime('%Y-%m-%d')
                        })

        return reminders_list

    @staticmethod
    def log_activity(campaign_id, user_id, activity_type, description):
        """Unified logging helper for visual activity timeline."""
        log = ActivityLog(
            campaign_id=campaign_id,
            user_id=user_id,
            activity_type=activity_type,
            description=description
        )
        db.session.add(log)
        db.session.commit()
