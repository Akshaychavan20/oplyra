"""Platform Admin access + route smoke tests (Internal Admin RBAC)."""
import unittest
from app import create_app, db
from app.models import User
from app.platform_admin.seed import seed_rbac, bootstrap_super_admin


class PlatformAdminAccessTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_rbac(commit=True)
        bootstrap_super_admin(commit=True)
        self.client = self.app.test_client()

        self.user = User(username='puser', email='user@oplyra.test')
        self.user.set_password('Pass1234!')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _customer_login(self, identity):
        return self.client.post('/login', data={
            'email_or_username': identity,
            'password': 'Pass1234!',
        }, follow_redirects=True)

    def _admin_login(self):
        self.client.get('/admin/login')
        with self.client.session_transaction() as sess:
            token = sess.get('csrf_token', '')
        return self.client.post('/admin/login', data={
            'email': 'admin@oplyra.test',
            'password': 'AdminBootstrap1!',
            'csrf_token': token,
        }, follow_redirects=True)

    def test_non_admin_forbidden(self):
        self._customer_login('user@oplyra.test')
        resp = self.client.get('/admin/', follow_redirects=False)
        self.assertIn(resp.status_code, (302, 401, 403))
        if resp.status_code in (301, 302):
            self.assertIn('/admin/login', resp.headers.get('Location', ''))

    def test_admin_overview_ok(self):
        resp = self._admin_login()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Platform Admin', resp.data)
        self.assertIn(b'Total Users', resp.data)

    def test_user_nav_has_ai_studio_not_tools(self):
        self._customer_login('user@oplyra.test')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI Studio', resp.data)
        self.assertIn(b'>Files</span>', resp.data)
        self.assertNotIn(b'id="sidebar-tools"', resp.data)
        self.assertNotIn(b'id="sidebar-tasks"', resp.data)


if __name__ == '__main__':
    unittest.main()
