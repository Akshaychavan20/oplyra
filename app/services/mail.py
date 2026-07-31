"""SMTP email delivery for Oplyra (password reset and future transactional mail).

Credentials come from app config / environment variables — never hardcoded.
Supports sync send (used by Celery workers) and async queueing.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER'))


def send_email_sync(
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    sender: Optional[str] = None,
) -> bool:
    """
    Send one email via SMTP. Returns True on success.
    Never logs message bodies that may contain secrets (reset links).
    """
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        logger.info('MAIL_SUPPRESS_SEND — email to %s skipped (subject=%s)', to, subject)
        return True

    mail_server = current_app.config.get('MAIL_SERVER')
    if not mail_server:
        logger.info('MAIL_SERVER unset — email to %s skipped (subject=%s)', to, subject)
        return False

    mail_port = int(current_app.config.get('MAIL_PORT') or 587)
    mail_use_tls = bool(current_app.config.get('MAIL_USE_TLS', True))
    mail_use_ssl = bool(current_app.config.get('MAIL_USE_SSL', False))
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    mail_sender = sender or current_app.config.get('MAIL_DEFAULT_SENDER') or 'no-reply@oplyra.com'

    msg = MIMEMultipart('alternative')
    msg['From'] = mail_sender
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        if mail_use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(mail_server, mail_port, timeout=30)
            if mail_use_tls:
                server.starttls(context=ssl.create_default_context())

        if mail_username and mail_password:
            server.login(mail_username, mail_password)

        server.sendmail(mail_sender, [to], msg.as_string())
        server.quit()
        logger.info('Email sent subject=%s to=%s', subject, to)
        return True
    except Exception as exc:
        logger.error('SMTP send failed to=%s error=%s', to, type(exc).__name__)
        return False


def render_password_reset_email(*, reset_link: str, expires_minutes: int = 30) -> tuple[str, str]:
    """Return (text_body, html_body) for the password-reset email.

    Uses the Jinja environment directly so Celery workers (no HTTP request /
    CSRF context) can render safely.
    """
    env = current_app.jinja_env
    ctx = {'reset_link': reset_link, 'expires_minutes': expires_minutes}
    text_body = env.get_template('email/password_reset.txt').render(**ctx)
    html_body = env.get_template('email/password_reset.html').render(**ctx)
    return text_body, html_body


def queue_email(
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> None:
    """
    Queue email asynchronously via Celery when available.
    Falls back to a daemon thread so the HTTP request is never blocked on SMTP.
    """
    if not _mail_configured() and not current_app.config.get('MAIL_SUPPRESS_SEND'):
        # Still attempt queue so tests can assert the task was called; sync path
        # will no-op cleanly when MAIL_SERVER is unset.
        pass

    try:
        from app.infra.tasks import send_email as send_email_task
        send_email_task.delay(
            to=to,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        return
    except Exception as exc:
        logger.warning('Celery enqueue failed (%s) — using thread fallback', type(exc).__name__)

    # Lightweight async fallback (extension point for SES/SendGrid later)
    import threading
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            send_email_sync(
                to=to,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )

    threading.Thread(target=_run, daemon=True, name='oplyra-mail').start()


def queue_password_reset_email(*, to: str, reset_link: str, expires_minutes: int = 30) -> None:
    """Build branded reset email and queue delivery."""
    text_body, html_body = render_password_reset_email(
        reset_link=reset_link,
        expires_minutes=expires_minutes,
    )
    queue_email(
        to=to,
        subject='Reset your Oplyra password',
        text_body=text_body,
        html_body=html_body,
    )
