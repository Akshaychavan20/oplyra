"""Clients CRM UX improvements — preserve existing /clients APIs."""
import unittest
import json
from app import create_app, db
from app.models import User, Project


class ClientsCrmUxTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(username='crm_user', email='crm@oplyra.test')
        self.user.set_password('Pass1234!')
        db.session.add(self.user)
        db.session.commit()

        self.project = Project(
            user_id=self.user.id,
            name='Acme Co',
            description='Performance marketing client',
        )
        db.session.add(self.project)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self):
        return self.client.post('/login', data={
            'email_or_username': 'crm_user',
            'password': 'Pass1234!',
        }, follow_redirects=True)

    def test_list_page_crm_chrome(self):
        self._login()
        resp = self.client.get('/clients/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Clients', resp.data)
        self.assertIn(b'clients-view-toggle', resp.data)
        self.assertIn(b'Acme Co', resp.data)
        # Sorting control present
        self.assertIn(b'clients-sort', resp.data)

    def test_detail_overview_and_quick_actions(self):
        self._login()
        resp = self.client.get(f'/clients/{self.project.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Quick actions', resp.data)
        self.assertIn(b'Generate Content', resp.data)
        self.assertIn(b'Open AI Studio', resp.data)
        self.assertIn(b'tab-overview', resp.data)
        self.assertIn(b'Company information', resp.data)
        self.assertIn(b'Recent timeline', resp.data)

    def test_toggle_pin_json(self):
        self._login()
        resp = self.client.post(f'/clients/{self.project.id}/toggle-pin')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('is_pinned'))

    def test_campaigns_preselect_from_client(self):
        self._login()
        resp = self.client.get(f'/content/campaigns/view?project_id={self.project.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'selected', resp.data)
        self.assertIn(str(self.project.id).encode(), resp.data)


if __name__ == '__main__':
    unittest.main()
