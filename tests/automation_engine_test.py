import unittest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Project, Campaign, CampaignLifecycleItem, Task, Note, Report, Organization, Membership, AutomationRule, Reminder, ActivityLog, TimelineMilestone
from app.services.automation_engine import AutomationEngine

class AutomationEngineTestCase(unittest.TestCase):
    """Unit tests for the Marketing Operations Automation Engine (Sprint 4)."""

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
        # 1. Setup Organization, User and Membership
        self.org = Organization(name="Automation Agency")
        db.session.add(self.org)
        db.session.commit()

        self.user = User(username='automator_bob', email='bob@oplyra.com')
        self.user.set_password('BobPass123!')
        db.session.add(self.user)
        db.session.commit()

        self.membership = Membership(user_id=self.user.id, organization_id=self.org.id, role='admin')
        db.session.add(self.membership)
        db.session.commit()

        # 2. Create Project
        self.project = Project(user_id=self.user.id, name="Test Brand Co", description="Testing playbooks")
        db.session.add(self.project)
        db.session.commit()

    def test_campaign_playbook_creation_wizard(self):
        # Run Campaign Creation from Gym Playbook
        campaign = AutomationEngine.create_campaign_from_wizard(
            user_id=self.user.id,
            org_id=self.org.id,
            project_id=self.project.id,
            name="Gym Summer Promotion",
            playbook_key="gym",
            goal="Lead Generation",
            platforms=["facebook", "google"],
            budget=800.00,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )

        # Assert campaign parameters
        self.assertIsNotNone(campaign.id)
        self.assertEqual(campaign.name, "Gym Summer Promotion")
        self.assertEqual(float(campaign.budget), 800.00)
        self.assertEqual(campaign.currency, 'INR')
        self.assertEqual(campaign.duration_type, 'fixed')
        self.assertIsNone(campaign.recurrence)

        # Assert Playbook Checklist items are seeded
        checklist_items = CampaignLifecycleItem.query.filter_by(campaign_id=campaign.id).all()
        self.assertTrue(len(checklist_items) > 0)
        stages = [item.stage for item in checklist_items]
        self.assertIn("Onboarding", stages)
        self.assertIn("Execution", stages)

        # Assert Playbook Notes template are pre-populated
        notes = Note.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, "Gym Membership Offer Sheet")

        # Assert default Automation rules toggled on
        rules = AutomationRule.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual(len(rules), 3)
        triggers = [r.trigger_type for r in rules]
        self.assertIn("deadline_tomorrow", triggers)
        self.assertIn("stage_start_reporting", triggers)

        # Assert Timeline Milestones are created
        milestones = TimelineMilestone.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual(len(milestones), 6)

    def test_workflow_automation_cloning(self):
        # 1. First, create a source campaign with tasks and notes
        src_campaign = Campaign(
            organization_id=self.org.id,
            project_id=self.project.id,
            name="Source Ads Campaign",
            type="social_campaign"
        )
        db.session.add(src_campaign)
        db.session.commit()

        # Add note and task
        src_task = Task(user_id=self.user.id, campaign_id=src_campaign.id, title="Custom Bidding Setup", status="pending")
        src_note = Note(user_id=self.user.id, campaign_id=src_campaign.id, title="Conversion Snippets", body="Important links here")
        db.session.add_all([src_task, src_note])
        db.session.commit()

        # 2. Deploy wizard with import option
        cloned_campaign = AutomationEngine.create_campaign_from_wizard(
            user_id=self.user.id,
            org_id=self.org.id,
            project_id=self.project.id,
            name="New Cloned Campaign",
            playbook_key="facebook_lead_gen",
            goal="Sales",
            platforms=["facebook"],
            budget=200.00,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=15),
            import_campaign_id=src_campaign.id
        )

        # Assert note and task cloned
        cloned_notes = Note.query.filter_by(campaign_id=cloned_campaign.id).all()
        cloned_titles = [n.title for n in cloned_notes]
        self.assertIn("[Copy] Conversion Snippets", cloned_titles)

        cloned_tasks = Task.query.filter_by(campaign_id=cloned_campaign.id).all()
        cloned_task_titles = [t.title for t in cloned_tasks]
        self.assertIn("Custom Bidding Setup", cloned_task_titles)

    def test_auto_task_generator(self):
        campaign = Campaign(
            organization_id=self.org.id,
            project_id=self.project.id,
            name="Direct Ads Pack",
            type="social_campaign",
            current_stage="Onboarding"
        )
        db.session.add(campaign)
        db.session.commit()

        # Move stage to Execution
        campaign.current_stage = "Execution"
        db.session.commit()

        # Trigger auto task generator
        created_tasks = AutomationEngine.generate_stage_tasks(campaign, "Execution")
        self.assertTrue(len(created_tasks) > 0)
        
        task_titles = [t.title for t in created_tasks]
        self.assertIn("Launch Live Campaigns", task_titles)
        self.assertIn("Install & Test Tracking Pixel", task_titles)

    def test_automation_rules_evaluation(self):
        campaign = Campaign(
            organization_id=self.org.id,
            project_id=self.project.id,
            name="Search Audit Campaign",
            type="seo",
            current_stage="Planning"
        )
        db.session.add(campaign)
        db.session.commit()

        # Seed rule to prepare report draft
        rule = AutomationRule(
            campaign_id=campaign.id,
            trigger_type="stage_start_reporting",
            action_type="prepare_report_draft",
            is_enabled=True
        )
        db.session.add(rule)
        db.session.commit()

        # Evaluate rule trigger
        AutomationEngine.evaluate_rules(campaign, "stage_start_reporting")

        # Verify a draft report was pre-compiled
        report = Report.query.filter_by(campaign_id=campaign.id, title="[Auto Draft] Campaign Summary Brief").first()
        self.assertIsNotNone(report)
        self.assertIn("WhatsApp Client Brief", report.content_markdown)
        self.assertIn("Email Template Draft", report.content_markdown)

        # Verify alert reminder was written
        reminder = Reminder.query.filter_by(campaign_id=campaign.id, title="Draft Report Ready").first()
        self.assertIsNotNone(reminder)

    def test_reminders_and_timeline_logging(self):
        campaign = Campaign(
            organization_id=self.org.id,
            project_id=self.project.id,
            name="Reminders Campaign",
            type="social_campaign",
            status="active"
        )
        db.session.add(campaign)
        db.session.commit()

        # Log timeline action
        AutomationEngine.log_activity(campaign.id, self.user.id, "task_completed", "Completed pixels check.")
        logs = ActivityLog.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].description, "Completed pixels check.")

        # Seed overdue task -> dynamic reminder
        overdue_task = Task(
            user_id=self.user.id,
            campaign_id=campaign.id,
            title="Old Campaign Review",
            status="pending",
            due_date=datetime.utcnow() - timedelta(days=4)
        )
        db.session.add(overdue_task)
        db.session.commit()

        reminders = AutomationEngine.get_reminders(self.user.id)
        titles = [r["title"] for r in reminders]
        self.assertIn("Task Overdue: Old Campaign Review", titles)
