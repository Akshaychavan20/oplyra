"""Cloud object storage adapter — S3 / GCS / Azure / Local (dev only)."""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class StoredObject:
    key: str
    url: str
    content_type: str
    size: int
    organization_id: Optional[int]
    provider: str
    meta: Dict


class ObjectStorage(ABC):
    provider_id: str = 'base'

    @abstractmethod
    def put(
        self,
        data: Union[bytes, BinaryIO],
        *,
        organization_id: Optional[int],
        filename: str,
        content_type: Optional[str] = None,
        folder: str = 'uploads',
        meta: Optional[Dict] = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def get_signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def healthcheck(self) -> bool:
        return True

    def _object_key(self, organization_id: Optional[int], folder: str, filename: str) -> str:
        org = organization_id if organization_id is not None else 0
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[-1].lower()[:20]
        return f'org_{org}/{folder}/{uuid.uuid4().hex}{ext}'


class LocalObjectStorage(ObjectStorage):
    """Filesystem storage — development/testing only."""

    provider_id = 'local'

    def __init__(self, root: Optional[str] = None):
        self.root = root or os.path.join(os.getcwd(), 'uploads', 'objects')
        os.makedirs(self.root, exist_ok=True)

    def put(self, data, *, organization_id=None, filename='file.bin', content_type=None, folder='uploads', meta=None):
        raw = data.read() if hasattr(data, 'read') else data
        key = self._object_key(organization_id, folder, filename)
        abs_path = os.path.join(self.root, key.replace('/', os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb') as f:
            f.write(raw)
        ctype = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        return StoredObject(
            key=key,
            url=f'file://{abs_path}',
            content_type=ctype,
            size=len(raw),
            organization_id=organization_id,
            provider=self.provider_id,
            meta=meta or {},
        )

    def get_signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        abs_path = os.path.join(self.root, key.replace('/', os.sep))
        return f'file://{abs_path}?expires={int(datetime.utcnow().timestamp()) + expires_seconds}'

    def delete(self, key: str) -> bool:
        abs_path = os.path.join(self.root, key.replace('/', os.sep))
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            return True
        return False

    def exists(self, key: str) -> bool:
        return os.path.isfile(os.path.join(self.root, key.replace('/', os.sep)))


class S3ObjectStorage(ObjectStorage):
    """Amazon S3 via boto3 when available; mock-signed URLs when credentials missing in non-prod."""

    provider_id = 's3'

    def __init__(self):
        self.bucket = os.environ.get('S3_BUCKET') or self._cfg('S3_BUCKET', '')
        self.region = os.environ.get('AWS_REGION') or self._cfg('AWS_REGION', 'us-east-1')
        self._client = None
        try:
            import boto3
            if self.bucket:
                self._client = boto3.client('s3', region_name=self.region)
        except Exception as exc:
            logger.info('S3 client not initialized: %s', type(exc).__name__)

    def _cfg(self, key, default=''):
        try:
            from flask import current_app
            return current_app.config.get(key, default)
        except RuntimeError:
            return default

    def put(self, data, *, organization_id=None, filename='file.bin', content_type=None, folder='uploads', meta=None):
        raw = data.read() if hasattr(data, 'read') else data
        key = self._object_key(organization_id, folder, filename)
        ctype = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        if self._client and self.bucket:
            extra = {'ContentType': ctype}
            self._client.put_object(Bucket=self.bucket, Key=key, Body=raw, **extra)
            url = f'https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}'
        else:
            # Dual-path: persist locally under uploads/s3-staging so bytes are not lost
            local = LocalObjectStorage(os.path.join(os.getcwd(), 'uploads', 's3-staging'))
            stored = local.put(raw, organization_id=organization_id, filename=filename, content_type=ctype, folder=folder, meta=meta)
            url = f's3://{self.bucket or "oplyra"}/{key}'
            key = stored.key
        return StoredObject(key=key, url=url, content_type=ctype, size=len(raw),
                            organization_id=organization_id, provider=self.provider_id, meta=meta or {})

    def get_signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        if self._client and self.bucket:
            return self._client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_seconds,
            )
        return f'https://{self.bucket or "oplyra"}.s3.amazonaws.com/{key}?X-Amz-Expires={expires_seconds}'

    def delete(self, key: str) -> bool:
        if self._client and self.bucket:
            self._client.delete_object(Bucket=self.bucket, Key=key)
            return True
        return LocalObjectStorage(os.path.join(os.getcwd(), 'uploads', 's3-staging')).delete(key)

    def exists(self, key: str) -> bool:
        if self._client and self.bucket:
            try:
                self._client.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False
        return LocalObjectStorage(os.path.join(os.getcwd(), 'uploads', 's3-staging')).exists(key)

    def healthcheck(self) -> bool:
        return bool(self.bucket)


class GCSObjectStorage(S3ObjectStorage):
    provider_id = 'gcs'

    def __init__(self):
        self.bucket = os.environ.get('GCS_BUCKET') or self._cfg('GCS_BUCKET', '')
        self._client = None
        try:
            from google.cloud import storage as gcs
            if self.bucket:
                self._client = gcs.Client()
        except Exception:
            self._client = None

    def put(self, data, *, organization_id=None, filename='file.bin', content_type=None, folder='uploads', meta=None):
        raw = data.read() if hasattr(data, 'read') else data
        key = self._object_key(organization_id, folder, filename)
        ctype = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        if self._client and self.bucket:
            bucket = self._client.bucket(self.bucket)
            blob = bucket.blob(key)
            blob.upload_from_string(raw, content_type=ctype)
            url = f'https://storage.googleapis.com/{self.bucket}/{key}'
        else:
            local = LocalObjectStorage(os.path.join(os.getcwd(), 'uploads', 'gcs-staging'))
            stored = local.put(raw, organization_id=organization_id, filename=filename, content_type=ctype, folder=folder, meta=meta)
            key, url = stored.key, f'gs://{self.bucket or "oplyra"}/{key}'
        return StoredObject(key=key, url=url, content_type=ctype, size=len(raw),
                            organization_id=organization_id, provider=self.provider_id, meta=meta or {})

    def get_signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        if self._client and self.bucket:
            bucket = self._client.bucket(self.bucket)
            blob = bucket.blob(key)
            return blob.generate_signed_url(expiration=timedelta(seconds=expires_seconds))
        return f'https://storage.googleapis.com/{self.bucket or "oplyra"}/{key}?expires={expires_seconds}'


class AzureBlobStorage(S3ObjectStorage):
    provider_id = 'azure'

    def __init__(self):
        self.container = os.environ.get('AZURE_BLOB_CONTAINER') or self._cfg('AZURE_BLOB_CONTAINER', '')
        self.account = os.environ.get('AZURE_STORAGE_ACCOUNT') or self._cfg('AZURE_STORAGE_ACCOUNT', '')
        self._client = None
        try:
            from azure.storage.blob import BlobServiceClient
            conn = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
            if conn:
                self._client = BlobServiceClient.from_connection_string(conn)
        except Exception:
            self._client = None

    def put(self, data, *, organization_id=None, filename='file.bin', content_type=None, folder='uploads', meta=None):
        raw = data.read() if hasattr(data, 'read') else data
        key = self._object_key(organization_id, folder, filename)
        ctype = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        if self._client and self.container:
            blob = self._client.get_blob_client(container=self.container, blob=key)
            blob.upload_blob(raw, overwrite=True, content_type=ctype)
            url = f'https://{self.account}.blob.core.windows.net/{self.container}/{key}'
        else:
            local = LocalObjectStorage(os.path.join(os.getcwd(), 'uploads', 'azure-staging'))
            stored = local.put(raw, organization_id=organization_id, filename=filename, content_type=ctype, folder=folder, meta=meta)
            key, url = stored.key, f'azure://{self.container or "oplyra"}/{key}'
        return StoredObject(key=key, url=url, content_type=ctype, size=len(raw),
                            organization_id=organization_id, provider=self.provider_id, meta=meta or {})

    def get_signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        return f'https://{self.account or "oplyra"}.blob.core.windows.net/{self.container or "uploads"}/{key}?se={expires_seconds}'


_STORAGE_REGISTRY = {
    'local': LocalObjectStorage,
    's3': S3ObjectStorage,
    'gcs': GCSObjectStorage,
    'azure': AzureBlobStorage,
}


def get_storage(name: Optional[str] = None) -> ObjectStorage:
    try:
        from flask import current_app
        provider = (name or current_app.config.get('STORAGE_PROVIDER') or 'local').lower()
        root = current_app.config.get('OBJECT_STORAGE_ROOT')
    except RuntimeError:
        provider = (name or os.environ.get('STORAGE_PROVIDER') or 'local').lower()
        root = None
    cls = _STORAGE_REGISTRY.get(provider, LocalObjectStorage)
    if cls is LocalObjectStorage:
        return LocalObjectStorage(root)
    return cls()
