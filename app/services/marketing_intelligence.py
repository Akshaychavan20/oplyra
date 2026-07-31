import json
from datetime import datetime, timedelta, date
from sqlalchemy import func
from app import db
from app.models import Campaign, CampaignLifecycleItem, Task, Note, Report, Project, Content, AnalyticsLog, AnalyticsMetrics

class MarketingIntelligenceEngine:
    """Marketing Intelligence Engine providing decision support for freelancers.
    
    Generates rule-based health checks, next actions, insights, risks, and opportunities 
    based solely on verified database workspace state.
    """

    @staticmethod
    def get_campaign_health(campaign):
        """Computes comprehensive health dashboard stats for a campaign."""
        items = CampaignLifecycleItem.query.filter_by(campaign_id=campaign.id).all()
        if not items:
            return {
                "overall_health": "Needs Attention",
                "stage_health": "0% complete",
                "trend": "Stable",
                "incomplete_areas": ["Checklist items not initialized"]
            }

        # Calculate stage progress
        stage_progress = campaign.get_stage_progress(campaign.current_stage)
        
        # Check overdue tasks
        today_date = date.today()
        overdue_tasks = Task.query.filter_by(campaign_id=campaign.id, status='pending', is_archived=False)\
            .filter(Task.due_date != None)\
            .all()
        overdue_count = sum(1 for t in overdue_tasks if t.due_date.date() < today_date)

        # Incomplete items in current stage
        incomplete_items = [it.name for it in items if it.stage.lower() == campaign.current_stage.lower() and not it.is_completed]

        # Calculate risks to determine health state
        has_missing_pixel = (campaign.current_stage.lower() in ['execution', 'monitoring'] and 
                             not any(it.is_completed for it in items if 'pixel' in it.name.lower() or 'tracking' in it.name.lower()))
        has_passed_deadline = (campaign.end_date and campaign.end_date < datetime.utcnow() and campaign.current_stage.lower() != 'completed')
        
        if has_missing_pixel or has_passed_deadline or overdue_count > 2:
            overall_health = "Critical"
        elif overdue_count > 0 or len(incomplete_items) > 3 or (campaign.budget or 0) <= 0:
            overall_health = "Needs Attention"
        elif stage_progress >= 75:
            overall_health = "Excellent"
        else:
            overall_health = "Good"

        # Determine trend
        recent_tasks_finished = Task.query.filter_by(campaign_id=campaign.id, status='completed')\
            .filter(Task.due_date >= datetime.utcnow() - timedelta(days=7))\
            .count()
            
        recent_notes_added = Note.query.filter_by(campaign_id=campaign.id)\
            .filter(Note.created_at >= datetime.utcnow() - timedelta(days=5))\
            .count()

        if recent_tasks_finished >= 2:
            trend = "Improving"
        elif recent_tasks_finished == 0 and recent_notes_added == 0 and overdue_count > 0:
            trend = "Declining"
        else:
            trend = "Stable"

        return {
            "overall_health": overall_health,
            "stage_health": f"{stage_progress}% stage complete",
            "trend": trend,
            "incomplete_areas": incomplete_items[:3] if incomplete_items else ["None - stage completed"]
        }

    @staticmethod
    def get_best_next_action(campaign):
        """Identifies exactly one best next action for a campaign."""
        items = CampaignLifecycleItem.query.filter_by(campaign_id=campaign.id).all()
        
        def is_item_complete(name_sub):
            return any(it.is_completed for it in items if name_sub.lower() in it.name.lower())

        # 1. Onboarding Checklist: Target Audience
        if campaign.current_stage.lower() == 'onboarding' and not is_item_complete('audience'):
            return {
                "action": "Define Target Audience Profile",
                "why": "No target audience persona or demographic segment has been check-marked in Onboarding.",
                "impact": "High",
                "time_est": "20 Minutes"
            }

        # 2. Overdue Tasks Check
        today_date = date.today()
        overdue_tasks = Task.query.filter_by(campaign_id=campaign.id, status='pending', is_archived=False)\
            .filter(Task.due_date != None)\
            .order_by(Task.due_date.asc())\
            .all()
        overdue_list = [t for t in overdue_tasks if t.due_date.date() < today_date]
        if overdue_list:
            top_overdue = overdue_list[0]
            return {
                "action": f"Complete: {top_overdue.title}",
                "why": "This campaign task is past its due date and blocks workflow execution.",
                "impact": "High",
                "time_est": "15 Minutes"
            }

        # 3. Strategy Approval in Planning Stage
        if campaign.current_stage.lower() == 'planning' and not is_item_complete('approval'):
            return {
                "action": "Obtain Client Strategy Approval",
                "why": "Obtaining approval completes the Planning Stage checklist and aligns client expectations.",
                "impact": "High",
                "time_est": "30 Minutes"
            }

        # 4. Tracking Setup in Execution Stage
        if campaign.current_stage.lower() == 'execution' and not is_item_complete('tracking'):
            return {
                "action": "Verify Tracking Pixel Setup",
                "why": "Tracking Setup is pending in the Execution checklist. Necessary to measure lead generation return on ad spend.",
                "impact": "High",
                "time_est": "15 Minutes"
            }

        # 5. Core Execution: Blog content
        if campaign.current_stage.lower() == 'execution' and not is_item_complete('blog'):
            return {
                "action": "Publish SEO Blog Content",
                "why": "Regular publishing is required to establish organic domain authority.",
                "impact": "Medium",
                "time_est": "25 Minutes"
            }

        # 6. Reporting checklist
        if campaign.current_stage.lower() == 'reporting' and not is_item_complete('report'):
            return {
                "action": "Compile Performance Brief Report",
                "why": "Reporting Stage is active. Delivering weekly KPI summaries improves client retention.",
                "impact": "High",
                "time_est": "10 Minutes"
            }

        # 7. Advance stage if current stage checklist is finished
        stage_progress = campaign.get_stage_progress(campaign.current_stage)
        if stage_progress == 100 and campaign.current_stage.lower() != 'completed':
            return {
                "action": "Advance Campaign Lifecycle Stage",
                "why": "All requirements for the current lifecycle stage are checked off.",
                "impact": "Medium",
                "time_est": "2 Minutes"
            }

        # 8. Next pending task fallback
        next_pending = Task.query.filter_by(campaign_id=campaign.id, status='pending', is_archived=False)\
            .order_by(Task.created_at.asc()).first()
        if next_pending:
            return {
                "action": f"Complete: {next_pending.title}",
                "why": "Actionable task pending in campaign checklist.",
                "impact": "Medium",
                "time_est": "15 Minutes"
            }

        # 9. Default Fallback
        return {
            "action": "Add Campaign Objectives",
            "why": "Ensure the campaign has planned tasks or target copywriting assets.",
            "impact": "Low",
            "time_est": "5 Minutes"
        }

    @staticmethod
    def get_smart_prioritized_tasks(campaign_id):
        """Categorizes pending tasks into High, Medium, and Low buckets using priority factors."""
        tasks = Task.query.filter_by(campaign_id=campaign_id, is_archived=False).all()
        high_tasks = []
        medium_tasks = []
        low_tasks = []
        
        today_date = date.today()
        
        for task in tasks:
            if task.status == 'completed':
                low_tasks.append(task)
                continue
                
            is_overdue = task.due_date and task.due_date.date() < today_date
            is_due_today = task.due_date and task.due_date.date() == today_date
            is_upcoming_soon = task.due_date and 0 < (task.due_date.date() - today_date).days <= 3
            
            if is_overdue or is_due_today or task.priority == 'high':
                high_tasks.append(task)
            elif is_upcoming_soon or task.priority == 'medium':
                medium_tasks.append(task)
            else:
                low_tasks.append(task)
                
        return {
            "high": high_tasks,
            "medium": medium_tasks,
            "low": low_tasks
        }

    @staticmethod
    def get_campaign_risks(campaign):
        """Identifies active business and tracking risks for the campaign."""
        items = CampaignLifecycleItem.query.filter_by(campaign_id=campaign.id).all()
        risks = []

        def is_item_complete(name_sub):
            return any(it.is_completed for it in items if name_sub.lower() in it.name.lower())

        # 1. Missing Tracking setup
        if campaign.current_stage.lower() in ['execution', 'monitoring'] and not is_item_complete('tracking'):
            risks.append({
                "title": "Tracking Pixel Missing",
                "why": "Tracking Pixel setup has not been checked in the active Execution stage.",
                "action": "Deploy Facebook Pixel or Google tracking code tags to the campaign landing page.",
                "impact": "High"
            })

        # 2. Budget limits unspecified
        if (campaign.budget or 0) <= 0:
            risks.append({
                "title": "Budget Unspecified",
                "why": "The target marketing campaign budget is zero.",
                "action": "Assign a monthly advertising limit in the campaign profile settings.",
                "impact": "Medium"
            })

        # 3. Overdue milestones
        today_date = date.today()
        overdue_tasks = Task.query.filter_by(campaign_id=campaign.id, status='pending', is_archived=False)\
            .filter(Task.due_date != None)\
            .all()
        overdue_count = sum(1 for t in overdue_tasks if t.due_date.date() < today_date)
        if overdue_count > 0:
            risks.append({
                "title": "Overdue Milestones",
                "why": f"There are currently {overdue_count} task(s) past their scheduled deadlines.",
                "action": "Complete or postpone overdue checklist tasks.",
                "impact": "High"
            })

        # 4. Weekly reporting missing
        if campaign.current_stage.lower() == 'reporting' and not is_item_complete('report'):
            risks.append({
                "title": "Reporting Gaps",
                "why": "No performance reports have been compiled or check-marked for delivery.",
                "action": "Compile and download a client KPI summary PDF in the reports panel.",
                "impact": "High"
            })

        # 5. Long inactivity
        recent_tasks_finished = Task.query.filter_by(campaign_id=campaign.id, status='completed')\
            .filter(Task.due_date >= datetime.utcnow() - timedelta(days=5))\
            .count()
        recent_notes = Note.query.filter_by(campaign_id=campaign.id)\
            .filter(Note.created_at >= datetime.utcnow() - timedelta(days=5))\
            .count()
        if recent_tasks_finished == 0 and recent_notes == 0:
            risks.append({
                "title": "Campaign Inactivity",
                "why": "No tasks completed or workspace optimization notes logged for five consecutive days.",
                "action": "Log an ad adjustment, perform keyword checks, or draft new copy elements.",
                "impact": "Medium"
            })

        return risks

    @staticmethod
    def get_campaign_opportunities(campaign):
        """Identifies opportunities to improve marketing outcomes."""
        opportunities = []

        # 1. Optimize Google Business Profile
        if campaign.type.lower() in ['seo', 'affiliate'] or 'local' in campaign.name.lower():
            opportunities.append({
                "title": "Optimize Google Business Profile",
                "why": "Google Business updates increase organic local search prominence by up to 18%.",
                "action": "Publish a weekly update post and verify search keyword maps.",
                "impact": "High",
                "time_est": "20 Minutes"
            })

        # 2. Boost blog publishing frequency (SEO-focused campaigns only)
        desc_lower = (campaign.description or '').lower()
        is_seo_focused = (
            campaign.type.lower() in ['seo', 'affiliate']
            or 'seo' in desc_lower
            or 'organic' in desc_lower
            or 'blog' in desc_lower
        )
        blog_assets_count = Content.query.filter_by(campaign_id=campaign.id, type='blog')\
            .filter(Content.generated_at >= datetime.utcnow() - timedelta(days=7))\
            .count()
        if blog_assets_count == 0 and is_seo_focused:
            opportunities.append({
                "title": "Boost Publishing Frequency",
                "why": "No blog posts have been generated in the last 7 days.",
                "action": "Generate and schedule an SEO blog article to maintain organic authority.",
                "impact": "Medium",
                "time_est": "25 Minutes"
            })

        # 3. Refresh ad creatives
        ad_files_count = Content.query.filter_by(campaign_id=campaign.id, type='ad_copy')\
            .filter(Content.generated_at >= datetime.utcnow() - timedelta(days=10))\
            .count()
        if ad_files_count == 0 and campaign.type.lower() in ['social_campaign', 'product_launch']:
            opportunities.append({
                "title": "Refresh Ad Creatives",
                "why": "Refreshing ad text periodically keeps click-through rate high and avoids creative fatigue.",
                "action": "Create a new social ad copy variant using the AI Studio.",
                "impact": "High",
                "time_est": "15 Minutes"
            })

        # 4. Landing page Conversion Audit
        if campaign.current_stage.lower() == 'execution':
            opportunities.append({
                "title": "Landing Page CRO Audit",
                "why": "Auditing headings and call-to-actions can double landing page conversion rates.",
                "action": "Audit call-to-action buttons and text alignment on key landing pages.",
                "impact": "High",
                "time_est": "30 Minutes"
            })

        return opportunities

    @staticmethod
    def get_campaign_insights(campaign):
        """Generates dynamic marketing insights and observations."""
        insights = []
        
        # Check inactivity
        recent_activity_count = Task.query.filter_by(campaign_id=campaign.id, status='completed')\
            .filter(Task.due_date >= datetime.utcnow() - timedelta(days=5))\
            .count()
        if recent_activity_count == 0:
            insights.append("No campaign activity for five days.")

        # Check stage speed
        stage_progress = campaign.get_stage_progress(campaign.current_stage)
        if campaign.current_stage.lower() in ['execution', 'monitoring'] and stage_progress >= 75:
            insights.append("SEO work is ahead of schedule.")

        # Check reporting status
        if campaign.current_stage.lower() == 'reporting' and stage_progress == 0:
            insights.append("Reporting stage has not started.")

        # Check CTR trend
        metrics = db.session.query(AnalyticsMetrics)\
            .join(Task, Task.id == AnalyticsMetrics.social_post_id)\
            .filter(Task.campaign_id == campaign.id)\
            .order_by(AnalyticsMetrics.record_date.desc())\
            .limit(2)\
            .all()
            
        if len(metrics) == 2:
            ctr_latest = float(metrics[0].clicks / metrics[0].impressions) if metrics[0].impressions > 0 else 0
            ctr_prev = float(metrics[1].clicks / metrics[1].impressions) if metrics[1].impressions > 0 else 0
            if ctr_latest < ctr_prev:
                insights.append("CTR decreased compared to last review.")

        return insights if insights else ["Campaign settings are stable. Work is progressing as scheduled."]

    @staticmethod
    def get_personalized_recommendations(campaign_id):
        """Generates structured, format-compliant recommendations for the sidebar widget."""
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return []

        recommendations = []
        
        # Pull risks and convert to recommendations format
        risks = MarketingIntelligenceEngine.get_campaign_risks(campaign)
        for idx, risk in enumerate(risks):
            conf = 90 - (idx * 6)
            recommendations.append({
                "priority": risk["impact"].lower(),
                "title": f"Review {risk['title']}",
                "why": risk["why"],
                "action": risk["action"],
                "consequence": "Negative impact on lead volumes and tracking visibility.",
                "time_est": "15 Minutes" if risk["impact"] == "High" else "10 Minutes",
                "impact": risk["impact"],
                "confidence": f"{conf}%"
            })

        # Pull opportunities and convert to recommendations format
        opps = MarketingIntelligenceEngine.get_campaign_opportunities(campaign)
        for idx, opp in enumerate(opps):
            conf = 85 - (idx * 5)
            recommendations.append({
                "priority": "low" if opp["impact"].lower() != "high" else "medium",
                "title": opp["title"],
                "why": opp["why"],
                "action": opp["action"],
                "consequence": "Loss of potential conversion gains and domain search visibility.",
                "time_est": opp["time_est"],
                "impact": opp["impact"],
                "confidence": f"{conf}%"
            })

        return recommendations

    @staticmethod
    def get_weekly_intelligence(user_id):
        """Aggregates platform wide activity over the past 7 days."""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        completed_campaigns = Campaign.query.join(Project)\
            .filter(Project.user_id == user_id, Campaign.current_stage == 'Completed', Campaign.created_at >= seven_days_ago)\
            .count()

        finished_tasks = Task.query.filter_by(user_id=user_id, status='completed')\
            .filter(Task.due_date >= seven_days_ago)\
            .count()

        delivered_reports = Report.query.filter_by(user_id=user_id)\
            .filter(Report.created_at >= seven_days_ago)\
            .count()

        user_campaigns = Campaign.query.join(Project).filter(Project.user_id == user_id).all()
        risk_count = 0
        for camp in user_campaigns:
            health = MarketingIntelligenceEngine.get_campaign_health(camp)
            if health["overall_health"] == "Critical":
                risk_count += 1

        recs = []
        if risk_count > 0:
            recs.append("Address critical campaigns immediately to prevent client churn.")
        if finished_tasks < 3:
            recs.append("Publish new SEO content or upload creative assets to increase workflow speed.")
        if delivered_reports == 0:
            recs.append("Compile a PDF report this week to maintain regular client metrics updates.")
            
        if not recs:
            recs.append("All campaigns are healthy. Focus on scheduling the next batch of content library uploads.")

        return {
            "completed_campaigns": completed_campaigns,
            "finished_tasks": finished_tasks,
            "delivered_reports": delivered_reports,
            "risk_count": risk_count,
            "recommendations": recs
        }

    @staticmethod
    def get_today_focus(user_id):
        """Identifies the critical item deserving the solopreneur's attention first."""
        user_campaigns = Campaign.query.join(Project).filter(Project.user_id == user_id).all()
        if not user_campaigns:
            return None

        health_rank = {"Critical": 1, "Needs Attention": 2, "Good": 3, "Excellent": 4}
        ranked_campaigns = []
        
        for camp in user_campaigns:
            health = MarketingIntelligenceEngine.get_campaign_health(camp)
            ranked_campaigns.append((camp, health, health_rank.get(health["overall_health"], 4)))
            
        ranked_campaigns.sort(key=lambda x: x[2])
        critical_camp, critical_health, _ = ranked_campaigns[0]
        
        bna = MarketingIntelligenceEngine.get_best_next_action(critical_camp)
        
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_completed = Task.query.filter_by(user_id=user_id, status='completed')\
            .filter(Task.due_date >= today_start).count()
        today_total = Task.query.filter_by(user_id=user_id)\
            .filter(Task.due_date >= today_start).count()

        reason = bna["why"]
        if critical_health["overall_health"] == "Critical":
            reason = "This campaign is in Critical condition and requires immediate intervention."

        upcoming = Task.query.filter_by(user_id=user_id, status='pending', is_archived=False)\
            .filter(Task.due_date != None)\
            .order_by(Task.due_date.asc()).first()
            
        deadline_str = "None pending"
        if upcoming:
            days_left = (upcoming.due_date.date() - date.today()).days
            if days_left == 0:
                deadline_str = "Today"
            elif days_left == 1:
                deadline_str = "Tomorrow"
            elif days_left > 1:
                deadline_str = upcoming.due_date.strftime('%b %d')
            else:
                deadline_str = f"Overdue ({abs(days_left)}d)"

        return {
            "campaign_id": critical_camp.id,
            "campaign_name": critical_camp.name,
            "action": bna["action"],
            "time_est": bna["time_est"],
            "deadline": deadline_str,
            "health": critical_health["overall_health"],
            "progress": f"{today_completed}/{today_total}" if today_total > 0 else "0/0",
            "reason": reason
        }
