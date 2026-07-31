"""Symmetric encryption for OAuth / integration tokens (fail-closed)."""
from __future__ import annotations

import base64
import hashlib
import logging

from flask import current_app

logger = logging.getLogger(__name__)


class TokenVaultError(RuntimeError):
    """Raised when credential encryption/decryption cannot proceed safely."""


def _fernet_key():
    secret = current_app.config.get('SECRET_KEY')
    if not secret:
        raise TokenVaultError('SECRET_KEY is not configured')
    hashed = hashlib.sha256(str(secret).encode('utf-8')).digest()
    return base64.urlsafe_b64encode(hashed)


def encrypt_token(value):
    """Encrypt a string credential. Never returns plaintext bytes."""
    if not value:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(_fernet_key()).encrypt(value.encode('utf-8'))
    except TokenVaultError:
        raise
    except Exception as exc:
        logger.error('Token encryption failed (fail-closed): %s', type(exc).__name__)
        raise TokenVaultError('Failed to encrypt credential') from exc


def decrypt_token(blob):
    """Decrypt a credential blob. Returns '' for empty; never returns plaintext guess."""
    if not blob:
        return ''
    try:
        from cryptography.fernet import Fernet
        return Fernet(_fernet_key()).decrypt(blob).decode('utf-8')
    except TokenVaultError:
        raise
    except Exception as exc:
        logger.error('Token decryption failed (fail-closed): %s', type(exc).__name__)
        raise TokenVaultError('Failed to decrypt credential') from exc
