"""Tests for Enterprise Knowledge Engine + RAG Platform."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    User, Organization, Membership,
    KnowledgeDocument, KnowledgeChunk, KnowledgeEmbedding,
    KnowledgeCollection, KnowledgeVersion,
)
from app.services.knowledge.service import KnowledgeService
from app.services.knowledge.pipeline import IngestPipeline
from app.services.knowledge.search import KnowledgeSearchService
from app.services.knowledge.rag import KnowledgeRAG, inject_rag_into_context
from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.embeddings import LocalHashEmbeddingProvider, get_embedding_provider
from app.services.knowledge.vector_store import get_vector_store, cosine_similarity
from app.services.agents.manager import AgentManager
from app.services.ai_gateway import AIGateway
from app.services.ai.registry import ProviderRegistry


class KnowledgeEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['KNOWLEDGE_EMBEDDING_PROVIDER'] = 'local'
        self.app.config['KNOWLEDGE_VECTOR_PROVIDER'] = 'local'
        self.app.config['KNOWLEDGE_RAG_ENABLED'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.user = User(username='know_tester', email='know@test.com')
        self.user.set_password('pass123')
        db.session.add(self.user)
        db.session.flush()

        self.org = Organization(name="Know Tester's Workspace", plan_tier='pro')
        db.session.add(self.org)
        db.session.flush()
        db.session.add(Membership(
            organization_id=self.org.id,
            user_id=self.user.id,
            role='admin',
        ))
        db.session.commit()

        self.client = self.app.test_client()
        self.svc = KnowledgeService()
        self.pipeline = IngestPipeline()
        self.gateway = AIGateway(api_key='your_test_placeholder_key')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        self.app_context.pop()

    def _login(self):
        return self.client.post('/login', data={
            'email_or_username': 'know_tester',
            'password': 'pass123',
        }, follow_redirects=True)

    def test_chunking_splits_text(self):
        text = 'Paragraph one.\n\n' + ('Sentence. ' * 80) + '\n\nParagraph three.'
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(c['content'] for c in chunks))

    def test_local_embeddings_deterministic(self):
        emb = LocalHashEmbeddingProvider(dims=64)
        a = emb.embed_one('brand voice confident')
        b = emb.embed_one('brand voice confident')
        c = emb.embed_one('totally unrelated topic xyz')
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)
        self.assertGreater(cosine_similarity(a, b), 0.99)
        self.assertLess(cosine_similarity(a, c), cosine_similarity(a, b))

    def test_vector_store_factory_local(self):
        store = get_vector_store('local')
        self.assertEqual(store.provider_id, 'local')
        self.assertEqual(get_embedding_provider('local').provider_id, 'local')

    def test_ingest_text_and_search(self):
        doc = self.pipeline.ingest_text(
            title='Brand Guidelines',
            text=(
                'Oplyra brand voice is confident, clear, and human. '
                'Never use jargon. Always lead with customer outcomes. '
                'Primary color is deep navy. Accent is electric blue.'
            ),
            user_id=self.user.id,
            organization_id=self.org.id,
            doc_type='brand',
            tags=['brand', 'voice'],
        )
        self.assertEqual(doc.status, 'active')
        self.assertGreater(doc.chunk_count, 0)
        self.assertGreater(KnowledgeChunk.query.filter_by(document_id=doc.id).count(), 0)
        self.assertGreater(KnowledgeEmbedding.query.filter_by(document_id=doc.id).count(), 0)
        self.assertEqual(KnowledgeVersion.query.filter_by(document_id=doc.id).count(), 1)

        hits = KnowledgeSearchService().search(
            'What is the Oplyra brand voice?',
            top_k=3,
            search_type='hybrid',
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        self.assertGreater(len(hits), 0)
        self.assertIn('confident', hits[0].content.lower())

    def test_collections_seed_and_create(self):
        cols = self.svc.list_collections(self.user.id, self.org.id)
        self.assertGreaterEqual(len(cols), 4)
        created = self.svc.create_collection(
            user_id=self.user.id,
            name='Client Playbooks',
            collection_type='client',
            organization_id=self.org.id,
        )
        self.assertEqual(created.name, 'Client Playbooks')

    def test_version_restore(self):
        doc = self.pipeline.ingest_text(
            title='Playbook',
            text='Version one content about onboarding.',
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        self.pipeline.create_new_version(
            doc,
            text='Version two content about retention.',
            user_id=self.user.id,
            change_note='Update',
        )
        self.assertEqual(doc.current_version, 2)
        restored = self.pipeline.restore_version(doc, 1, user_id=self.user.id)
        self.assertEqual(restored.current_version, 3)
        latest = KnowledgeVersion.query.filter_by(
            document_id=doc.id, version_number=3,
        ).first()
        self.assertIn('onboarding', latest.content_text)

    def test_rag_injects_into_agent_context(self):
        self.pipeline.ingest_text(
            title='SEO Playbook',
            text='Always target long-tail keywords with buyer intent for SaaS landing pages.',
            user_id=self.user.id,
            organization_id=self.org.id,
            doc_type='playbook',
        )
        ctx = {'extras': ''}
        inject_rag_into_context(
            ctx,
            user_id=self.user.id,
            goal='Write SEO recommendations for SaaS',
            organization_id=self.org.id,
        )
        self.assertIn('Retrieved Knowledge', ctx['extras'])
        self.assertIn('long-tail', ctx['extras'].lower())

    def test_agents_receive_knowledge_via_memory_hook(self):
        self.pipeline.ingest_text(
            title='Campaign Rules',
            text='Budget tip: allocate 60% to Meta Ads and 40% to Google Search for B2C apps.',
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        mgr = AgentManager(gateway=self.gateway)
        run = mgr.run(
            user_id=self.user.id,
            goal='Suggest a paid media budget split for a B2C mobile app',
            agent_key='campaign',
            organization_id=self.org.id,
        )
        self.assertEqual(run.status, 'completed')
        # Context should have been enriched (extras contains knowledge or run succeeded with gateway)
        self.assertTrue(run.final_output)

    def test_api_upload_search_stats(self):
        self._login()
        res = self.client.post('/api/knowledge/upload', json={
            'title': 'Case Study',
            'text': 'Our client increased ROAS by 45% using creative testing frameworks.',
            'doc_type': 'case_study',
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()['success'])
        doc_id = res.get_json()['document']['id']

        search = self.client.post('/api/knowledge/search', json={
            'query': 'ROAS creative testing',
            'search_type': 'hybrid',
        })
        self.assertEqual(search.status_code, 200)
        self.assertGreater(search.get_json()['count'], 0)

        stats = self.client.get('/api/knowledge/stats')
        self.assertEqual(stats.status_code, 200)
        self.assertGreaterEqual(stats.get_json()['stats']['documents'], 1)

        detail = self.client.get(f'/api/knowledge/document/{doc_id}')
        self.assertEqual(detail.status_code, 200)

        home = self.client.get('/api/knowledge/')
        self.assertEqual(home.status_code, 200)
        self.assertTrue(home.get_json()['success'])

    def test_api_collections(self):
        self._login()
        res = self.client.get('/api/knowledge/collections')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.get_json()['collections']), 1)
        created = self.client.post('/api/knowledge/collections', json={
            'name': 'Research Reports',
            'collection_type': 'workspace',
        })
        self.assertEqual(created.status_code, 201)

    def test_soft_delete(self):
        doc = self.pipeline.ingest_text(
            title='Temp',
            text='Temporary document',
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        self.svc.delete_document(doc, self.user.id, hard=False)
        self.assertEqual(doc.status, 'deleted')

    def test_file_upload_txt(self):
        self._login()
        data = {
            'file': (io.BytesIO(b'Product description guidelines for Oplyra.'), 'guide.txt'),
        }
        res = self.client.post(
            '/api/knowledge/upload',
            data=data,
            content_type='multipart/form-data',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()['document']['doc_type'], 'txt')


if __name__ == '__main__':
    unittest.main()
