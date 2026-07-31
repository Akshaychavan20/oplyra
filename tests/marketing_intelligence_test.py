import unittest
from datetime import datetime, timedelta, date
from app import create_app, db
from app.models import User, Project, Campaign, CampaignLifecycleItem, Task, Note, Report, Organization, Membership
from app.services.marketing_intelligence import MarketingIntelligenceEngine

class MarketingIntelligenceTestCase(unittest.TestCase):
    """Unit tests for the Marketing Intelligence decision support engines."""

    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.seed_mock_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def seed_mock_data(self):
        # 1. Setup agency organization, user, and membership
        self.org = Organization(name="SaaS Intelligence Agency")
        db.session.add(self.org)
        db.session.commit()

        self.user = User(username='analyst_akshay', email='analyst@oplyra.com')
        self.user.set_password('SecurityP@ss1')
        db.session.add(self.user)
        db.session.commit()

        self.membership = Membership(user_id=self.user.id, organization_id=self.org.id, role='admin')
        db.session.add(self.membership)
        db.session.commit()

        # 2. Create Project
        self.project = Project(user_id=self.user.id, name="ABC Business", description="Retail client")
        db.session.add(self.project)
        db.session.commit()

        # 3. Create Campaign
        self.campaign = Campaign(
            project_id=self.project.id,
            organization_id=self.org.id,
            name="Google Search Ad Pack",
            type="seo",
            description="Q3 client local search optimization",
            budget=1500,
            current_stage="Onboarding"
        )
        db.session.add(self.campaign)
        db.session.commit()

        # Seed lifecycle checklist items
        self.check_audience = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Onboarding", name="Target Audience", is_completed=False)
        self.check_setup = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Onboarding", name="Initial Checklists", is_completed=True)
        self.check_approval = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Planning", name="Approval", is_completed=False)
        self.check_pixel = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Execution", name="Tracking Setup", is_completed=False)
        self.check_blog = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Execution", name="Blog", is_completed=False)
        self.check_report = CampaignLifecycleItem(campaign_id=self.campaign.id, stage="Reporting", name="Weekly Report", is_completed=False)
        
        db.session.add_all([self.check_audience, self.check_setup, self.check_approval, self.check_pixel, self.check_blog, self.check_report])
        db.session.commit()

    def test_campaign_health_states(self):
        # Default: Onboarding stage, incomplete audience checklist, budget exists, no overdue tasks.
        # Health should be "Needs Attention" because checklist is incomplete, or "Good" if no overdue tasks/critical risks.
        health = MarketingIntelligenceEngine.get_campaign_health(self.campaign)
        self.assertIn("overall_health", health)
        self.assertIn("stage_health", health)
        self.assertIn("trend", health)
        
        # Now make campaign budget 0
        self.campaign.budget = 0
        db.session.commit()
        health_no_budget = MarketingIntelligenceEngine.get_campaign_health(self.campaign)
        self.assertEqual(health_no_budget["overall_health"], "Needs Attention")

        # Now advance to Execution stage with missing pixel check -> Critical health
        self.campaign.current_stage = "Execution"
        self.campaign.budget = 2000
        db.session.commit()
        health_exec_no_pixel = MarketingIntelligenceEngine.get_campaign_health(self.campaign)
        self.assertEqual(health_exec_no_pixel["overall_health"], "Critical")

    def test_best_next_action_matching(self):
        # 1. Onboarding with incomplete audience -> "Define Target Audience Profile"
        self.campaign.current_stage = "Onboarding"
        db.session.commit()
        bna = MarketingIntelligenceEngine.get_best_next_action(self.campaign)
        self.assertEqual(bna["action"], "Define Target Audience Profile")
        self.assertEqual(bna["impact"], "High")

        # Complete audience, advance to Planning -> "Obtain Client Strategy Approval"
        self.check_audience.is_completed = True
        self.campaign.current_stage = "Planning"
        db.session.commit()
        bna_planning = MarketingIntelligenceEngine.get_best_next_action(self.campaign)
        self.assertEqual(bna_planning["action"], "Obtain Client Strategy Approval")

        # Advance to Execution -> "Verify Tracking Pixel Setup"
        self.campaign.current_stage = "Execution"
        db.session.commit()
        bna_exec = MarketingIntelligenceEngine.get_best_next_action(self.campaign)
        self.assertEqual(bna_exec["action"], "Verify Tracking Pixel Setup")

    def test_smart_prioritized_tasks(self):
        # Seed tasks
        t_high = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Crit Task", priority="high", status="pending")
        t_overdue = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Overdue Task", priority="medium", status="pending", due_date=datetime.utcnow() - timedelta(days=2))
        t_due_today = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Today Task", priority="low", status="pending", due_date=datetime.utcnow())
        t_med = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Med Task", priority="medium", status="pending")
        t_low = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Low Task", priority="low", status="pending")
        
        db.session.add_all([t_high, t_overdue, t_due_today, t_med, t_low])
        db.session.commit()

        buckets = MarketingIntelligenceEngine.get_smart_prioritized_tasks(self.campaign.id)
        
        # Verify buckets
        high_titles = [t.title for t in buckets["high"]]
        med_titles = [t.title for t in buckets["medium"]]
        low_titles = [t.title for t in buckets["low"]]

        self.assertIn("Crit Task", high_titles)
        self.assertIn("Overdue Task", high_titles)
        self.assertIn("Today Task", high_titles)
        self.assertIn("Med Task", med_titles)
        self.assertIn("Low Task", low_titles)

    def test_recommendations_compliance(self):
        recs = MarketingIntelligenceEngine.get_personalized_recommendations(self.campaign.id)
        self.assertTrue(len(recs) > 0)
        
        for r in recs:
            self.assertIn("priority", r)
            self.assertIn("title", r)
            self.assertIn("why", r)
            self.assertIn("action", r)
            self.assertIn("consequence", r)
            self.assertIn("time_est", r)
            self.assertIn("impact", r)
            self.assertIn("confidence", r)

            # Ensure strict non-empty content
            self.assertTrue(bool(r["why"].strip()))
            self.assertTrue(bool(r["action"].strip()))
            self.assertTrue(bool(r["consequence"].strip()))
            self.assertTrue(bool(r["confidence"].strip()))

    def test_weekly_intelligence(self):
        # Create a finished task and report this week
        finished = Task(user_id=self.user.id, campaign_id=self.campaign.id, title="Done task", status="completed", due_date=datetime.utcnow() - timedelta(days=1))
        rep = Report(user_id=self.user.id, campaign_id=self.campaign.id, project_id=self.project.id, title="Weekly Brief", content_markdown="KPI summary")
        db.session.add_all([finished, rep])
        db.session.commit()

        summary = MarketingIntelligenceEngine.get_weekly_intelligence(self.user.id)
        self.assertEqual(summary["finished_tasks"], 1)
        self.assertEqual(summary["delivered_reports"], 1)
        self.assertTrue(len(summary["recommendations"]) > 0)
