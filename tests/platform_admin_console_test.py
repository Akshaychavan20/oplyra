"""Platform Admin full console tests — Internal Admin RBAC gate + page smoke."""
import unittest
from app import create_app, db
from app.models import User, Project
from app.platform_admin.seed import seed_rbac, bootstrap_super_admin


class PlatformAdminConsoleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_rbac(commit=True)
        bootstrap_super_admin(commit=True)
        self.client = self.app.test_client()

        # Customer users (cannot access /admin via customer login)
        self.user = User(username='puser2', email='user2@oplyra.test')
        self.user.set_password('Pass1234!')
        db.session.add(self.user)
        db.session.commit()
        self.project = Project(user_id=self.user.id, name='Client A')
        db.session.add(self.project)
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

    def test_customer_dashboard_untouched_labels(self):
        self._customer_login('user2@oplyra.test')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI Studio', resp.data)
        self.assertNotIn(b'pa-sidebar', resp.data)

    def test_non_admin_forbidden_on_pages(self):
        self._customer_login('user2@oplyra.test')
        for path in (
            '/admin/', '/admin/users', '/admin/ai-analytics', '/admin/monitoring',
            '/admin/feature-flags', '/admin/settings', '/admin/agents',
        ):
            resp = self.client.get(path, follow_redirects=False)
            self.assertIn(resp.status_code, (302, 401, 403), path)
            if resp.status_code in (301, 302):
                self.assertIn('/admin/login', resp.headers.get('Location', ''), path)

    def test_admin_pages_ok(self):
        self._admin_login()
        paths = [
            '/admin/',
            '/admin/users',
            f'/admin/users/{self.user.id}',
            '/admin/subscriptions',
            '/admin/billing',
            '/admin/ai-analytics',
            '/admin/ai-providers',
            '/admin/agents',
            '/admin/knowledge',
            '/admin/tools',
            '/admin/storage',
            '/admin/infrastructure',
            '/admin/monitoring',
            '/admin/audit',
            '/admin/feature-flags',
            '/admin/settings',
            '/admin/organizations',
        ]
        for path in paths:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, f'{path} -> {resp.status_code}')
            self.assertIn(b'Platform Admin', resp.data)

    def test_suspend_activate_and_reset(self):
        self._admin_login()
        resp = self.client.post(f'/admin/users/{self.user.id}/suspend', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Suspended', resp.data)

        resp = self.client.post(f'/admin/users/{self.user.id}/activate', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Active', resp.data)

        resp = self.client.post(f'/admin/users/{self.user.id}/reset-password', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Password reset link created', resp.data)
        self.assertNotIn(b'Pass1234!', resp.data)
        # Raw reset URL must not be flashed into the admin UI
        self.assertNotIn(b'/reset-password/', resp.data)

    def test_feature_flag_toggle(self):
        self._admin_login()
        resp = self.client.post('/admin/feature-flags', data={
            'key': 'maintenance_mode',
            'enabled': '1',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'maintenance_mode', resp.data)

    def test_legacy_section_redirect(self):
        self._admin_login()
        resp = self.client.get('/admin/section/agents', follow_redirects=False)
        self.assertIn(resp.status_code, (301, 302))

    def test_theme_system_inheritance(self):
        """Admin chrome must inherit global design tokens — no parallel palette."""
        self._admin_login()
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('css/style.css', html)
        self.assertIn('css/platform-admin.css', html)
        self.assertIn('js/theme.js', html)
        self.assertIn('theme-toggle-btn', html)
        self.assertIn('data-theme', html)
        self.assertNotIn('text-white', html)
        # Unified page shell — every admin page must use this hierarchy
        self.assertIn('pa-main', html)
        self.assertIn('pa-page', html)
        self.assertIn('pa-page-header', html)
        self.assertIn('pa-page-body', html)

        import os
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        css_path = os.path.join(root, 'app', 'static', 'css', 'platform-admin.css')
        with open(css_path, encoding='utf-8') as fh:
            css = fh.read()

        for token in (
            '--bg-dark',
            '--card-bg',
            '--text-primary',
            '--text-secondary',
            '--border-subtle',
            '--primary-hsl',
            '--success',
            '--warning',
            '--danger',
            '--hover-overlay',
            '--surface-chrome',
            '--surface-input',
            '--bs-body-bg',
            '--surface-elevated',
            '--surface-dropdown',
            '--surface-modal',
        ):
            self.assertIn(token, css, f'missing token {token}')

        # Dark-theme surface hardening must exist (no translucent white bleed)
        self.assertIn('html[data-theme="dark"] .pa-app .glass-card', css)
        self.assertIn('--pa-surface-solid', css)
        # Closed overlays must not paint (black strip / flash)
        self.assertIn('.pa-drawer-overlay.is-open', css)
        self.assertIn('visibility: hidden', css)

        # Layout shell contract — header never sticky; body is sole scrollport
        self.assertIn('--pa-page-header-min-height', css)
        self.assertIn('.pa-page-body', css)
        self.assertRegex(css, r'\.pa-page-body\s*\{[^}]*overflow-y:\s*auto')
        self.assertRegex(
            css,
            r'\.pa-page-header\s*\{[^}]*position:\s*relative',
            'pa-page-header must be relative (not sticky/fixed)',
        )
        self.assertNotRegex(
            css,
            r'\.pa-page-header\s*\{[^}]*position:\s*sticky',
            'pa-page-header must not use position:sticky',
        )

        for bad in ('--bg-primary', '--bg-secondary', '#0b0d12', '#a5b4fc', '#6ee7b7', '#fcd34d'):
            self.assertNotIn(bad, css, f'forbidden color/token {bad}')

        analytics = self.client.get('/admin/ai-analytics')
        self.assertEqual(analytics.status_code, 200)
        body = analytics.data.decode('utf-8')
        self.assertIn('OplyraTheme', body)
        self.assertIn('oplyra:themechange', body)
        self.assertIn('pa-page-body', body)
        self.assertNotIn('#818cf8', body)
        self.assertNotIn('#34d399', body)

        # Every console page template must inherit the shared shell
        tpl_dir = os.path.join(root, 'app', 'templates', 'platform_admin')
        skip = {'base_admin.html', 'base_admin_auth.html', 'login.html'}
        for name in os.listdir(tpl_dir):
            if not name.endswith('.html') or name in skip:
                continue
            path = os.path.join(tpl_dir, name)
            if not os.path.isfile(path):
                continue
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            self.assertIn(
                "extends 'platform_admin/base_admin.html'",
                src,
                f'{name} must extend base_admin.html for unified layout',
            )
            self.assertNotIn('page-content', src, f'{name} must not use customer .page-content wrapper')
            self.assertNotIn('position: sticky', src.lower())
            self.assertNotIn('position:sticky', src.lower())


if __name__ == '__main__':
    unittest.main()
