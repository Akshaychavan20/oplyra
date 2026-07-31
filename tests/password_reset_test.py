"""Production password-reset flow — security, tokens, rate limits, email."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.models import AuthSecurityLog, PasswordResetToken, User
from app.services.password_reset import (
    GENERIC_FORGOT_MESSAGE,
    SUCCESS_RESET_MESSAGE,
    hash_reset_token,
    issue_reset_token,
)


STRONG_PASSWORD = 'SecurePass1!'
WEAK_PASSWORD = 'weak'


def _assert_flash_contains(resp, text: str):
    """Flash messages are Jinja-escaped in HTML (e.g. we&#39;ve)."""
    body = resp.data.decode('utf-8', errors='ignore')
    if text in body:
        return
    # Common HTML entity escapes
    escaped = (
        text.replace('&', '&amp;')
        .replace("'", '&#39;')
        .replace('"', '&#34;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
    if escaped not in body:
        raise AssertionError(f'Expected flash text not found: {text!r}')


class PasswordResetTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(username='resetuser', email='reset@oplyra.test')
        self.user.set_password('OldPass123!')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _forgot(self, email, follow=True):
        return self.client.post(
            '/forgot-password',
            data={'email': email},
            follow_redirects=follow,
        )

    def _reset(self, token, password, confirm=None, follow=True):
        return self.client.post(
            f'/reset-password/{token}',
            data={
                'password': password,
                'confirm_password': confirm if confirm is not None else password,
            },
            follow_redirects=follow,
        )

    # ── Forgot password ───────────────────────────────────────────────────

    def test_forgot_existing_email_generic_message(self):
        with patch('app.auth.routes.send_reset_email') as mock_send:
            resp = self._forgot('reset@oplyra.test')
        self.assertEqual(resp.status_code, 200)
        _assert_flash_contains(resp, GENERIC_FORGOT_MESSAGE)
        mock_send.assert_called_once()
        self.assertEqual(PasswordResetToken.query.filter_by(user_id=self.user.id).count(), 1)
        row = PasswordResetToken.query.first()
        self.assertEqual(len(row.token_hash), 64)
        self.assertNotIn(mock_send.call_args[0][1], row.token_hash)  # raw link not stored as hash alone check
        # Plaintext token must not appear in DB column values
        self.assertFalse(hasattr(row, 'token') and getattr(row, 'token', None))

    def test_forgot_unknown_email_same_message(self):
        with patch('app.auth.routes.send_reset_email') as mock_send:
            resp = self._forgot('nobody@oplyra.test')
        self.assertEqual(resp.status_code, 200)
        _assert_flash_contains(resp, GENERIC_FORGOT_MESSAGE)
        mock_send.assert_not_called()
        self.assertEqual(PasswordResetToken.query.count(), 0)
        self.assertNotIn(b'not found', resp.data.lower())
        self.assertNotIn(b'does not exist', resp.data.lower())

    def test_forgot_invalid_email_format(self):
        resp = self.client.post('/forgot-password', data={'email': 'not-an-email'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'valid email', resp.data.lower())

    def test_token_stored_as_hash_only(self):
        with self.app.test_request_context('/', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            raw, row = issue_reset_token(self.user)
        self.assertEqual(row.token_hash, hash_reset_token(raw))
        self.assertNotEqual(row.token_hash, raw)

    def test_multiple_requests_only_newest_valid(self):
        with self.app.test_request_context('/'):
            raw1, row1 = issue_reset_token(self.user)
            raw2, row2 = issue_reset_token(self.user)
        db.session.refresh(row1)
        self.assertTrue(row1.used)
        self.assertIsNotNone(row1.used_at)
        self.assertFalse(row2.used)
        # Old token rejected
        resp = self.client.get(f'/reset-password/{raw1}', follow_redirects=True)
        self.assertIn(b'invalid', resp.data.lower())
        # New token accepted
        resp2 = self.client.get(f'/reset-password/{raw2}')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Reset Password', resp2.data)

    # ── Reset password ────────────────────────────────────────────────────

    def test_successful_reset(self):
        with self.app.test_request_context('/'):
            raw, row = issue_reset_token(self.user)
        resp = self._reset(raw, STRONG_PASSWORD)
        self.assertEqual(resp.status_code, 200)
        _assert_flash_contains(resp, SUCCESS_RESET_MESSAGE)
        db.session.refresh(self.user)
        db.session.refresh(row)
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))
        self.assertFalse(self.user.check_password('OldPass123!'))
        self.assertTrue(row.used)
        self.assertIsNotNone(row.used_at)
        events = [e.event_type for e in AuthSecurityLog.query.all()]
        self.assertIn('password_reset_success', events)

    def test_weak_password_rejected(self):
        with self.app.test_request_context('/'):
            raw, _ = issue_reset_token(self.user)
        resp = self._reset(raw, WEAK_PASSWORD)
        self.assertIn(b'at least 8', resp.data.lower())
        db.session.refresh(self.user)
        self.assertTrue(self.user.check_password('OldPass123!'))

    def test_strong_password_accepted(self):
        with self.app.test_request_context('/'):
            raw, _ = issue_reset_token(self.user)
        resp = self._reset(raw, 'AnotherGood9#')
        _assert_flash_contains(resp, SUCCESS_RESET_MESSAGE)

    def test_expired_token(self):
        with self.app.test_request_context('/'):
            raw, row = issue_reset_token(self.user)
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        resp = self.client.get(f'/reset-password/{raw}', follow_redirects=True)
        self.assertIn(b'expired', resp.data.lower())
        events = [e.event_type for e in AuthSecurityLog.query.all()]
        self.assertIn('password_reset_expired_token', events)

    def test_used_token_rejected(self):
        with self.app.test_request_context('/'):
            raw, row = issue_reset_token(self.user)
        row.mark_used()
        db.session.commit()
        resp = self.client.get(f'/reset-password/{raw}', follow_redirects=True)
        self.assertIn(b'invalid', resp.data.lower())

    def test_invalid_token(self):
        resp = self.client.get('/reset-password/not-a-real-token', follow_redirects=True)
        self.assertIn(b'invalid', resp.data.lower())
        events = [e.event_type for e in AuthSecurityLog.query.all()]
        self.assertIn('password_reset_invalid_token', events)

    def test_replay_attack(self):
        with self.app.test_request_context('/'):
            raw, _ = issue_reset_token(self.user)
        self._reset(raw, STRONG_PASSWORD)
        # Replay same token
        resp = self._reset(raw, 'SecondPass9!')
        self.assertIn(b'invalid', resp.data.lower())
        db.session.refresh(self.user)
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))
        self.assertFalse(self.user.check_password('SecondPass9!'))

    def test_validate_token_endpoint(self):
        with self.app.test_request_context('/'):
            raw, _ = issue_reset_token(self.user)
        ok = self.client.get(f'/reset-password/{raw}/validate')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.get_json()['valid'])
        bad = self.client.get('/reset-password/bogus/validate')
        self.assertFalse(bad.get_json()['valid'])
        self.assertEqual(bad.get_json()['status'], 'missing')

    # ── Rate limiting ─────────────────────────────────────────────────────

    def test_rate_limit_email(self):
        with patch('app.auth.routes.send_reset_email'):
            for _ in range(5):
                resp = self._forgot('reset@oplyra.test')
                self.assertEqual(resp.status_code, 200)
            resp = self._forgot('reset@oplyra.test', follow=False)
            # follow_redirects False — 429 may be returned with template
            if resp.status_code == 302:
                resp = self.client.get(resp.headers['Location'])
            # After 5, next should be rate limited
            resp6 = self.client.post(
                '/forgot-password',
                data={'email': 'reset@oplyra.test'},
                follow_redirects=True,
            )
            self.assertTrue(
                resp6.status_code == 429 or b'Too many' in resp6.data,
                msg=f'expected rate limit, got {resp6.status_code}',
            )
            events = [e.event_type for e in AuthSecurityLog.query.all()]
            self.assertIn('password_reset_rate_limit_exceeded', events)

    # ── Email ─────────────────────────────────────────────────────────────

    def test_email_queue_invoked(self):
        with patch('app.services.mail.queue_password_reset_email') as mock_q:
            # Call through real send_reset_email
            from app.auth.routes import send_reset_email
            send_reset_email('reset@oplyra.test', 'http://example/reset/abc', user_id=self.user.id)
            mock_q.assert_called_once()
            kwargs = mock_q.call_args.kwargs
            self.assertEqual(kwargs['to'], 'reset@oplyra.test')
            self.assertIn('reset', kwargs['reset_link'])

    def test_email_templates_render(self):
        from app.services.mail import render_password_reset_email
        text, html = render_password_reset_email(
            reset_link='https://oplyra.test/reset-password/tok',
            expires_minutes=30,
        )
        self.assertIn('Reset Password', html)
        self.assertIn('https://oplyra.test/reset-password/tok', text)
        self.assertIn('30 minutes', text)
        self.assertIn('Oplyra', html)

    def test_smtp_send_suppressed_in_tests(self):
        from app.services.mail import send_email_sync
        ok = send_email_sync(
            to='a@b.com',
            subject='t',
            text_body='hello',
            html_body='<p>hello</p>',
        )
        self.assertTrue(ok)  # MAIL_SUPPRESS_SEND => True without SMTP

    def test_passwords_never_in_security_logs(self):
        with self.app.test_request_context('/'):
            raw, _ = issue_reset_token(self.user)
        self._reset(raw, STRONG_PASSWORD)
        for row in AuthSecurityLog.query.all():
            blob = (row.details or '') + (row.event_type or '')
            self.assertNotIn(STRONG_PASSWORD, blob)
            self.assertNotIn(raw, blob)


if __name__ == '__main__':
    unittest.main()
