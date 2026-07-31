"""Phase 2 infrastructure — storage, vector, redis, celery, health, rate limits."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, Organization, Membership, KnowledgeDocument, BackgroundJob
from app.services.ai.registry import ProviderRegistry
from app.infra.redis_client import get_redis, reset_redis_client, cache_set, cache_get, MemoryRedis
from app.infra.storage import get_storage, LocalObjectStorage, S3ObjectStorage
from app.infra.rate_limit import check_rate_limit, RateLimitExceeded, enforce_rate_limit
from app.infra.metrics import incr, snapshot, reset_metrics
from app.infra.tasks import retention_cleanup, enqueue_job
from app.services.knowledge.vector_store import get_vector_store, LocalVectorStore
from app.services.knowledge.vector_providers import QdrantVectorStore, PineconeVectorStore, PgVectorStore
from config import ProductionConfig


class Phase2InfraTestCase(unittest.TestCase):
    def setUp(self):
        reset_redis_client()
        reset_metrics()
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.user = User(username='p2_user', email='p2@test.com')
        self.user.set_password('Pass1234!')
        db.session.add(self.user)
        db.session.flush()
        self.org = Organization(name='P2 Org', plan_tier='pro')
        db.session.add(self.org)
        db.session.flush()
        db.session.add(Membership(
            organization_id=self.org.id, user_id=self.user.id, role='admin',
        ))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        reset_redis_client()
        self.app_context.pop()

    def _login(self):
        self.client.post('/login', data={
            'email_or_username': 'p2_user',
            'password': 'Pass1234!',
        })

    # --- Redis / cache ---

    def test_redis_memory_fallback(self):
        client = get_redis()
        self.assertIsInstance(client, MemoryRedis)
        self.assertTrue(client.ping())
        cache_set('hello', 'world', ttl_seconds=60)
        self.assertEqual(cache_get('hello'), 'world')

    # --- Storage ---

    def test_local_storage_uuid_org_isolation(self):
        storage = LocalObjectStorage()
        obj = storage.put(
            b'hello-bytes',
            organization_id=self.org.id,
            filename='brand.pdf',
            content_type='application/pdf',
            folder='knowledge',
        )
        self.assertTrue(obj.key.startswith(f'org_{self.org.id}/'))
        self.assertIn(obj.provider, ('local',))
        self.assertTrue(storage.exists(obj.key))
        url = storage.get_signed_url(obj.key, expires_seconds=120)
        self.assertTrue(url.startswith('file://'))
        self.assertTrue(storage.delete(obj.key))

    def test_storage_factory_respects_config(self):
        store = get_storage('local')
        self.assertEqual(store.provider_id, 'local')
        s3 = get_storage('s3')
        self.assertEqual(s3.provider_id, 's3')

    def test_knowledge_upload_uses_storage(self):
        self._login()
        from io import BytesIO
        data = {
            'title': 'Infra Guide',
        }
        res = self.client.post(
            '/api/knowledge/upload',
            data={
                'title': 'Infra Guide',
                'file': (BytesIO(b'# Hello knowledge'), 'infra.md'),
            },
            content_type='multipart/form-data',
        )
        self.assertIn(res.status_code, (200, 201))
        body = res.get_json()
        self.assertTrue(body.get('success'))
        doc = KnowledgeDocument.query.get(body['document']['id'])
        self.assertIsNotNone(doc.source_uri)

    # --- Vector providers ---

    def test_local_vector_is_capped_store(self):
        store = get_vector_store('local')
        self.assertIsInstance(store, LocalVectorStore)
        self.assertTrue(store.healthcheck())

    def test_qdrant_falls_back_without_url(self):
        store = QdrantVectorStore()
        self.assertFalse(store._configured())
        self.assertEqual(store.provider_id, 'qdrant')

    def test_pinecone_and_pgvector_construct(self):
        self.assertEqual(PineconeVectorStore().provider_id, 'pinecone')
        self.assertEqual(PgVectorStore().provider_id, 'pgvector')

    def test_production_forbids_local_vector(self):
        class App:
            def __init__(self):
                self.config = {
                    'SECRET_KEY': 'a' * 32,
                    'SQLALCHEMY_DATABASE_URI': 'mysql+pymysql://u:p@localhost/oplyra',
                    'KNOWLEDGE_VECTOR_PROVIDER': 'local',
                    'STORAGE_PROVIDER': 's3',
                    'ALLOW_LOCAL_INFRA': False,
                }
        with self.assertRaises(RuntimeError) as ctx:
            ProductionConfig.init_app(App())
        self.assertIn('vector', str(ctx.exception).lower())

    def test_production_forbids_local_storage(self):
        class App:
            def __init__(self):
                self.config = {
                    'SECRET_KEY': 'a' * 32,
                    'SQLALCHEMY_DATABASE_URI': 'mysql+pymysql://u:p@localhost/oplyra',
                    'KNOWLEDGE_VECTOR_PROVIDER': 'qdrant',
                    'STORAGE_PROVIDER': 'local',
                    'ALLOW_LOCAL_INFRA': False,
                }
        with self.assertRaises(RuntimeError) as ctx:
            ProductionConfig.init_app(App())
        self.assertIn('storage', str(ctx.exception).lower())

    # --- Celery / jobs ---

    def test_celery_eager_retention_job(self):
        result = retention_cleanup.apply(kwargs={'days': 90}).get()
        self.assertIn('deleted', result)

    def test_enqueue_job_creates_row(self):
        job = enqueue_job(
            'retention_cleanup',
            user_id=self.user.id,
            organization_id=self.org.id,
            payload={'days': 30},
            days=30,
        )
        self.assertIn(job['status'], ('queued', 'running', 'completed'))
        row = BackgroundJob.query.get(job['id'])
        self.assertIsNotNone(row)

    # --- Rate limiting ---

    def test_rate_limit_blocks_after_quota(self):
        reset_redis_client()
        for _ in range(20):
            ok, _, _ = check_rate_limit('auth', identity='ip:1.2.3.4', limit=20, window_seconds=60)
            self.assertTrue(ok)
        ok, remaining, retry = check_rate_limit('auth', identity='ip:1.2.3.4', limit=20, window_seconds=60)
        self.assertFalse(ok)
        self.assertEqual(remaining, 0)

    def test_enforce_raises(self):
        reset_redis_client()
        for _ in range(3):
            enforce_rate_limit('admin', identity='u:1', organization_id=1)
        # tighten via loop with tiny limit
        with self.assertRaises(RateLimitExceeded):
            for _ in range(50):
                enforce_rate_limit('admin', identity='u:burst')

    # --- Health / metrics ---

    def test_live_ready_health_metrics(self):
        live = self.client.get('/live')
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.get_json()['status'], 'alive')

        ready = self.client.get('/ready')
        self.assertEqual(ready.status_code, 200)

        health = self.client.get('/health')
        self.assertEqual(health.status_code, 200)
        self.assertIn('checks', health.get_json())

        incr('ai.requests', 2)
        metrics = self.client.get('/metrics')
        self.assertEqual(metrics.status_code, 200)
        self.assertGreaterEqual(metrics.get_json()['metrics']['ai_requests'], 2)

    def test_security_headers_still_present(self):
        res = self.client.get('/live')
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')


if __name__ == '__main__':
    unittest.main()
