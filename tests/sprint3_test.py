import unittest
import json
import io
import zipfile
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Project, Campaign, Content, SEOAnalysis, AnalyticsLog, Organization, Membership
from app.services.seo_service import SEOAnalyzer

class Sprint3TestCase(unittest.TestCase):
    """Unit and integration test cases covering Sprint 3 Content Library and SEO changes."""

    def setUp(self):
        # Configure app for testing with in-memory SQLite
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Initialize tables
        db.create_all()

        # Seed mock database objects
        self.seed_mock_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def seed_mock_data(self):
        # 0. Create SaaS Organization and User Membership
        self.org = Organization(name="Test Org Agency")
        db.session.add(self.org)
        db.session.commit()

        # 1. Create User
        self.user = User(username='testmarketer', email='test@oplyra.com')
        self.user.set_password('Password123!')
        db.session.add(self.user)
        db.session.commit()

        self.membership = Membership(user_id=self.user.id, organization_id=self.org.id, role='admin')
        db.session.add(self.membership)
        db.session.commit()

        # 2. Create Projects (Workspaces)
        self.proj_active = Project(user_id=self.user.id, name='Active Widget Co', description='Performance marketing for widgets')
        self.proj_other = Project(user_id=self.user.id, name='Other SaaS Brand', description='Affiliate niche SaaS reviews')
        db.session.add(self.proj_active)
        db.session.add(self.proj_other)
        db.session.commit()

        # 3. Create Campaign with organization link
        self.camp = Campaign(project_id=self.proj_active.id, organization_id=self.org.id, name='Summer Promo Launch', type='affiliate')
        db.session.add(self.camp)
        db.session.commit()

        # 4. Create Contents
        self.c1 = Content(
            project_id=self.proj_active.id,
            campaign_id=self.camp.id,
            organization_id=self.org.id,
            title='Top 5 Wireless Blenders',
            body='# Top 5 Wireless Blenders\n\nLooking for the best wireless blenders? Here is our comprehensive list.\n\n## 1. Smart Blender Pro\nThis is a high quality blender designed for smoothies on the run.\n\n## Conclusion\nBuy the smart blender pro today!',
            type='blog',
            prompt_used='Write a blog about blenders',
            status='draft',
            is_favorite=False,
            generated_at=datetime.utcnow() - timedelta(days=2)
        )
        self.c2 = Content(
            project_id=self.proj_active.id,
            organization_id=self.org.id,
            title='ASUS ROG Laptop Review',
            body='# ASUS ROG Laptop Review\n\nAn incredible high-FPS machine designed for competitive gaming.',
            type='product_review',
            prompt_used='Write a product review for ASUS ROG',
            status='published',
            is_favorite=True,
            generated_at=datetime.utcnow() - timedelta(days=15)
        )
        self.c3 = Content(
            project_id=self.proj_other.id,
            organization_id=self.org.id,
            title='Email Campaign Draft',
            body='# Promo Offer\n\nGet 20% discount on standard checkout fees today.',
            type='email',
            prompt_used='Write a promotional email campaign',
            status='draft',
            is_favorite=False,
            generated_at=datetime.utcnow()
        )
        db.session.add_all([self.c1, self.c2, self.c3])
        db.session.commit()

        # 5. Add SEO Analysis to c1
        self.seo_analysis = SEOAnalysis(
            content_id=self.c1.id,
            keywords_found={"blender": 1},
            seo_score=85,
            readability_score=72,
            suggestions=['Add alt tags to images', 'Increase internal link counts'],
            details={
                "readability": {"flesch_reading_ease": 72.0, "rating": "Fairly Easy"},
                "structure": {"h1_count": 1, "h2_count": 2, "h3_count": 0, "h4_count": 0, "nested_header_issues": []},
                "links": {"internal_link_count": 0, "external_link_count": 0, "links": []},
                "images": {"image_count": 0, "images_missing_alt_count": 0, "images": []},
                "voice": {"passive_voice_percentage": 5.0},
                "paragraphs": {"total_paragraphs": 3, "long_paragraphs_count": 0},
                "sentences": {"total_sentences": 6, "long_sentences_count": 0}
            }
        )
        db.session.add(self.seo_analysis)
        db.session.commit()

    def login_test_user(self):
        """Simulates Flask Login login event."""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True

    def test_seo_analyzer_service(self):
        """Directly tests the backend SEOAnalyzer metrics parser logic."""
        text = (
            "# Best Blender 2026\n\n"
            "This blender is extremely fast. We tested this blender for three weeks.\n\n"
            "## Key Features\n"
            "The blender has five blades. However, a passive voice is used by the machine.\n\n"
            "## Conclusion\n"
            "Buy this blender."
        )
        
        # Test analysis with blender keyword
        result = SEOAnalyzer.analyze('Best Blender 2026', text, ['blender'])
        
        self.assertIn('readability_score', result)
        self.assertIn('seo_score', result)
        self.assertIn('details', result)
        self.assertGreaterEqual(result['details']['heading_analysis']['h1_count'], 1)
        self.assertGreaterEqual(result['details']['heading_analysis']['h2_count'], 2)
        self.assertGreater(result['details']['passive_voice']['density_percent'], 0.0)

    def test_content_library_pagination_and_filters(self):
        """Verifies filtering, searching, and sorting parameters on Content Library GET route."""
        self.login_test_user()
        
        # 1. Search filter
        resp = self.client.get('/content/library?q=Blenders')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Top 5 Wireless Blenders', resp.data)
        self.assertNotIn(b'ASUS ROG Laptop Review', resp.data)

        # 2. Type filter
        resp = self.client.get('/content/library?type=email')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Email Campaign Draft', resp.data)
        self.assertNotIn(b'ASUS ROG Laptop Review', resp.data)

        # 3. Favorites only filter
        resp = self.client.get('/content/library?favorites=true')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'ASUS ROG Laptop Review', resp.data)
        self.assertNotIn(b'Top 5 Wireless Blenders', resp.data)

        # 4. Sorting test: newest
        resp = self.client.get('/content/library?sort_by=newest')
        self.assertEqual(resp.status_code, 200)
        # Check order: Email Campaign Draft (created now) is before ASUS ROG Laptop Review (created 15 days ago)
        idx_email = resp.data.index(b'Email Campaign Draft')
        idx_asus = resp.data.index(b'ASUS ROG Laptop Review')
        self.assertLess(idx_email, idx_asus)

    def test_bulk_action_endpoints(self):
        """Verifies bulk edit POST endpoint for favoriting, deleting, moving, and exports."""
        self.login_test_user()

        # 1. Bulk Favorite
        resp = self.client.post('/content/api/bulk-action', 
            data=json.dumps({'action': 'favorite', 'ids': [self.c1.id, self.c3.id]}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Content.query.get(self.c1.id).is_favorite)
        self.assertTrue(Content.query.get(self.c3.id).is_favorite)

        # 2. Bulk Move
        resp = self.client.post('/content/api/bulk-action',
            data=json.dumps({'action': 'move', 'ids': [self.c1.id], 'project_id': self.proj_other.id}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Content.query.get(self.c1.id).project_id, self.proj_other.id)

        # 3. Bulk Soft Delete
        resp = self.client.post('/content/api/bulk-action',
            data=json.dumps({'action': 'delete', 'ids': [self.c1.id, self.c2.id]}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Content.query.get(self.c1.id).status, 'deleted')
        self.assertEqual(Content.query.get(self.c2.id).status, 'deleted')

        # 4. Bulk ZIP Export (Markdown format)
        resp = self.client.post('/content/api/bulk-action',
            data=json.dumps({'action': 'export', 'ids': [self.c3.id], 'export_format': 'markdown'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/zip')
        
        # Verify ZIP contains file with correct contents
        zip_file = zipfile.ZipFile(io.BytesIO(resp.data))
        file_list = zip_file.namelist()
        self.assertEqual(len(file_list), 1)
        self.assertIn('Email_Campaign_Draft.md', file_list[0])
        self.assertIn(b'Get 20% discount', zip_file.read(file_list[0]))

    def test_analytics_dashboard_timeframes(self):
        """Verifies dynamic timeframe parameter processing in analytics dashboard."""
        self.login_test_user()

        # Seed mock analytics usage log
        log = AnalyticsLog(user_id=self.user.id, activity_type='generate_blog', token_usage=1500, created_at=datetime.utcnow() - timedelta(days=5))
        db.session.add(log)
        db.session.commit()

        # 1. Test 7d timeframe
        resp = self.client.get('/api/analytics/dashboard?timeframe=7d')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(len(data['timeframe_activity']['counts']), 7)
        self.assertEqual(data['timeframe'], '7d')

        # 2. Test 90d timeframe
        resp = self.client.get('/api/analytics/dashboard?timeframe=90d')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(len(data['timeframe_activity']['counts']), 90)
        self.assertEqual(data['timeframe'], '90d')

    def test_project_workspace_duplication(self):
        """Verifies recursive duplication of projects, campaigns, tasks, and notes."""
        self.login_test_user()

        # Seed a task and note
        from app.models import Task, Note
        task = Task(user_id=self.user.id, project_id=self.proj_active.id, title='Review copy')
        note = Note(project_id=self.proj_active.id, user_id=self.user.id, title='Client specs', body='Focus on smoothies')
        db.session.add_all([task, note])
        db.session.commit()

        # Duplicate the workspace
        resp = self.client.post(f'/clients/{self.proj_active.id}/duplicate')
        self.assertEqual(resp.status_code, 302) # Redirects to new workspace detail page

        # Verify duplicated workspace exists in database
        dup_project = Project.query.filter_by(name='Copy of Active Widget Co').first()
        self.assertIsNotNone(dup_project)
        
        # Verify children items were copied
        self.assertEqual(len(dup_project.campaigns), 1)
        self.assertEqual(len(dup_project.contents), 2)
        self.assertEqual(len(dup_project.tasks), 1)
        self.assertEqual(len(dup_project.notes), 1)

if __name__ == '__main__':
    unittest.main()
