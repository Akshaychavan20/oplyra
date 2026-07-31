"""Internal Admin RBAC — isolation, login, permission matrix tests."""
import unittest
from app import create_app, db
from app.models import User
from app.platform_admin.models import AdminUser, AdminRole
from app.platform_admin.seed import seed_rbac, bootstrap_super_admin
from app.platform_admin.permissions import ROLE_MATRIX


class InternalAdminRbacTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_rbac(commit=True)
        bootstrap_super_admin(commit=True)
        self.client = self.app.test_client()

        self.customer = User(username='cust1', email='customer@oplyra.test')
        self.customer.set_password('Pass1234!')
        db.session.add(self.customer)
        db.session.commit()

        # Ensure finance role admin for matrix tests
        finance = AdminRole.query.filter_by(slug='finance').first()
        self.finance_admin = AdminUser(
            email='finance@oplyra.test',
            full_name='Finance User',
            role_id=finance.id,
            status=AdminUser.STATUS_ACTIVE,
        )
        self.finance_admin.set_password('FinancePass1!')
        db.session.add(self.finance_admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _csrf(self):
        # Hit login page to establish session + csrf
        self.client.get('/admin/login')
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token', '')

    def _admin_login(self, email, password):
        token = self._csrf()
        return self.client.post('/admin/login', data={
            'email': email,
            'password': password,
            'csrf_token': token,
        }, follow_redirects=True)

    def _customer_login(self):
        return self.client.post('/login', data={
            'email_or_username': 'customer@oplyra.test',
            'password': 'Pass1234!',
        }, follow_redirects=True)

    def test_bootstrap_super_admin_exists(self):
        admin = AdminUser.query.filter_by(email='admin@oplyra.test').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role.slug, 'super_admin')
        self.assertTrue(admin.has_permission('users:impersonate'))
        self.assertTrue(admin.has_permission('admins:manage'))

    def test_role_matrix_seeded(self):
        for slug in ROLE_MATRIX:
            role = AdminRole.query.filter_by(slug=slug).first()
            self.assertIsNotNone(role, slug)
            codes = {p.code for p in role.permissions}
            if slug == 'super_admin':
                self.assertIn('admin:all', codes)
            else:
                for code in ROLE_MATRIX[slug]:
                    self.assertIn(code, codes, f'{slug} missing {code}')

    def test_customer_session_cannot_access_admin(self):
        self._customer_login()
        resp = self.client.get('/admin/')
        # Redirect to internal login (not 200 with console)
        self.assertIn(resp.status_code, (302, 401, 403))
        if resp.status_code in (301, 302):
            self.assertIn('/admin/login', resp.headers.get('Location', ''))

    def test_customer_login_form_not_admin(self):
        """Even matching PLATFORM_ADMIN_EMAILS customer User is not enough."""
        # Create customer with same email as bootstrap admin — still separate password/store
        twin = User(username='admintwin', email='admin@oplyra.test')
        twin.set_password('Pass1234!')
        db.session.add(twin)
        db.session.commit()
        self.client.post('/login', data={
            'email_or_username': 'admin@oplyra.test',
            'password': 'Pass1234!',
        }, follow_redirects=True)
        resp = self.client.get('/admin/')
        self.assertIn(resp.status_code, (302, 401, 403))

    def test_super_admin_login_and_overview(self):
        resp = self._admin_login('admin@oplyra.test', 'AdminBootstrap1!')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Platform Admin', resp.data)
        self.assertIn(b'Total Users', resp.data)

    def test_bad_password_rejected(self):
        resp = self._admin_login('admin@oplyra.test', 'WrongPass1!')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Invalid email or password', resp.data)

    def test_finance_cannot_access_users(self):
        self._admin_login('finance@oplyra.test', 'FinancePass1!')
        resp = self.client.get('/admin/users')
        self.assertEqual(resp.status_code, 403)

    def test_finance_can_access_billing(self):
        self._admin_login('finance@oplyra.test', 'FinancePass1!')
        resp = self.client.get('/admin/billing')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Platform Admin', resp.data)

    def test_unauthenticated_redirects_to_admin_login(self):
        resp = self.client.get('/admin/monitoring', follow_redirects=False)
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn('/admin/login', resp.headers.get('Location', ''))

    def test_stale_bootstrap_password_sync_in_debug(self):
        """Changing INTERNAL_ADMIN_BOOTSTRAP_PASSWORD must re-hash via Flask-Bcrypt."""
        from app.platform_admin.seed import sync_bootstrap_admin_password

        admin = AdminUser.query.filter_by(email='admin@oplyra.test').first()
        self.assertIsNotNone(admin)
        # Simulate stale hash (old bootstrap password)
        admin.set_password('AdminBootstrap1!')
        admin.failed_login_count = 5
        from datetime import datetime, timedelta
        admin.locked_until = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()

        self.assertTrue(admin.check_password('AdminBootstrap1!'))
        self.assertFalse(admin.check_password('NewBootstrap9!'))

        # Env still points at AdminBootstrap1! in TestingConfig — change it
        self.app.config['INTERNAL_ADMIN_BOOTSTRAP_PASSWORD'] = 'NewBootstrap9!'
        self.app.config['INTERNAL_ADMIN_BOOTSTRAP_EMAIL'] = 'admin@oplyra.test'
        synced = sync_bootstrap_admin_password(commit=True)
        self.assertTrue(synced)

        db.session.refresh(admin)
        self.assertTrue(admin.check_password('NewBootstrap9!'))
        self.assertFalse(admin.check_password('AdminBootstrap1!'))
        self.assertEqual(admin.failed_login_count, 0)
        self.assertIsNone(admin.locked_until)

        # Same library end-to-end through login helper
        resp = self._admin_login_with('admin@oplyra.test', 'NewBootstrap9!')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Platform Admin', resp.data)

    def _admin_login_with(self, email, password):
        self.client.get('/admin/login')
        with self.client.session_transaction() as sess:
            token = sess.get('csrf_token', '')
        return self.client.post('/admin/login', data={
            'email': email,
            'password': password,
            'csrf_token': token,
        }, follow_redirects=True)


if __name__ == '__main__':
    unittest.main()
