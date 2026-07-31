"""Embedding provider abstraction — never hardcode a single vendor."""
from __future__ import annotations

import hashlib
import math
import os
import struct
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from flask import current_app


class EmbeddingProvider(ABC):
    provider_id: str = 'base'
    model: str = 'default'
    dims: int = 384

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for tests / offline. No external API."""

    provider_id = 'local'

    def __init__(self, dims: int = 384, model: str = 'local-hash-384'):
        self.dims = dims
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dims
        tokens = (text or '').lower().split()
        if not tokens:
            tokens = ['empty']
        for tok in tokens:
            digest = hashlib.sha256(tok.encode('utf-8')).digest()
            # Mix multiple 4-byte ints into dimensions
            for i in range(0, min(len(digest), 32), 4):
                val = struct.unpack('>I', digest[i:i + 4])[0]
                idx = val % self.dims
                vec[idx] += 1.0
            # Bi-grams for better local similarity
            for j in range(len(tok) - 1):
                bg = tok[j:j + 2]
                d2 = hashlib.md5(bg.encode('utf-8')).digest()
                idx2 = struct.unpack('>I', d2[:4])[0] % self.dims
                vec[idx2] += 0.5
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_id = 'openai'

    def __init__(self, api_key: Optional[str] = None, model: str = 'text-embedding-3-small', dims: int = 1536):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.model = model
        self.dims = dims

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key or str(self.api_key).startswith('your_'):
            return LocalHashEmbeddingProvider(dims=self.dims).embed(texts)
        resp = requests.post(
            'https://api.openai.com/v1/embeddings',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={'model': self.model, 'input': texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()['data']
        data.sort(key=lambda x: x['index'])
        vectors = [row['embedding'] for row in data]
        self.dims = len(vectors[0]) if vectors else self.dims
        return vectors


class GeminiEmbeddingProvider(EmbeddingProvider):
    provider_id = 'gemini'

    def __init__(self, api_key: Optional[str] = None, model: str = 'text-embedding-004', dims: int = 768):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        self.model = model
        self.dims = dims

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key or str(self.api_key).startswith('your_'):
            return LocalHashEmbeddingProvider(dims=self.dims).embed(texts)
        # Prefer google-genai if available; fallback to local on failure
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            out = []
            for t in texts:
                result = client.models.embed_content(model=self.model, contents=t)
                emb = list(result.embeddings[0].values)
                out.append(emb)
            if out:
                self.dims = len(out[0])
            return out
        except Exception:
            return LocalHashEmbeddingProvider(dims=self.dims).embed(texts)


class ClaudeCompatibleEmbeddingProvider(EmbeddingProvider):
    """Placeholder for Claude-compatible / OpenAI-compatible embedding endpoints."""

    provider_id = 'claude_compatible'

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = 'text-embedding-3-small',
        dims: int = 1536,
    ):
        self.api_key = api_key or os.environ.get('OPENAI_COMPATIBLE_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
        self.base_url = (base_url or os.environ.get('OPENAI_COMPATIBLE_BASE_URL') or '').rstrip('/')
        self.model = model
        self.dims = dims

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key or not self.base_url or str(self.api_key).startswith('your_'):
            return LocalHashEmbeddingProvider(dims=self.dims).embed(texts)
        resp = requests.post(
            f'{self.base_url}/embeddings',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={'model': self.model, 'input': texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()['data']
        data.sort(key=lambda x: x['index'])
        return [row['embedding'] for row in data]


def get_embedding_provider(name: Optional[str] = None) -> EmbeddingProvider:
    try:
        cfg = current_app.config
        provider = (name or cfg.get('KNOWLEDGE_EMBEDDING_PROVIDER') or 'local').lower()
        dims = int(cfg.get('KNOWLEDGE_EMBEDDING_DIMS') or 384)
        model = cfg.get('KNOWLEDGE_EMBEDDING_MODEL') or 'local-hash-384'
    except RuntimeError:
        provider = (name or os.environ.get('KNOWLEDGE_EMBEDDING_PROVIDER') or 'local').lower()
        dims = int(os.environ.get('KNOWLEDGE_EMBEDDING_DIMS') or 384)
        model = os.environ.get('KNOWLEDGE_EMBEDDING_MODEL') or 'local-hash-384'

    if provider in ('openai',):
        return OpenAIEmbeddingProvider(model=model if 'embed' in model else 'text-embedding-3-small')
    if provider in ('gemini', 'google'):
        return GeminiEmbeddingProvider()
    if provider in ('claude', 'claude_compatible', 'openai_compatible'):
        return ClaudeCompatibleEmbeddingProvider()
    return LocalHashEmbeddingProvider(dims=dims, model=model)
