"""
Oplyra AI Gateway — public facade.

Backward-compatible with existing callers:
  text, tokens = AIGateway().generate(prompt, system_instruction, model, user_id)

Internally routes through ProviderRegistry + TaskRouter + fallback chain.
Provider SDKs must not be imported by routes — only this module (and provider adapters).
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Generator, Optional, Tuple

from flask import current_app

from app.services.ai.catalog import estimate_cost, infer_provider_from_model
from app.services.ai.pipeline import PromptPipeline
from app.services.ai.registry import ProviderRegistry
from app.services.ai.router import TaskRouter
from app.services.ai.types import AIRequest, AIResponse, ProviderId, TaskType

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Legacy export — Gemini default when no routing preference is set
DEFAULT_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')


class AIGateway:
    """Production multi-provider AI gateway with cache, billing, routing, and fallback."""

    def __init__(self, api_key=None, redis_url=None, registry: Optional[ProviderRegistry] = None):
        # Legacy gemini key injection (GeminiService still passes api_key)
        self.api_key = api_key
        if not self.api_key:
            try:
                if current_app:
                    self.api_key = current_app.config.get('GEMINI_API_KEY')
            except RuntimeError:
                pass
        if not self.api_key:
            self.api_key = os.environ.get('GEMINI_API_KEY')

        self.registry = registry or ProviderRegistry.instance()
        # If an explicit Gemini key was provided, override registry gemini adapter
        if self.api_key:
            gemini = self.registry.get(ProviderId.GEMINI)
            if gemini:
                gemini.api_key = self.api_key

        self.router = TaskRouter(self.registry)
        self.pipeline = PromptPipeline()

        self.redis_client = None
        if REDIS_AVAILABLE:
            r_url = redis_url or os.environ.get('REDIS_URL')
            if not r_url:
                try:
                    if current_app:
                        r_url = current_app.config.get('CELERY_BROKER_URL')
                except RuntimeError:
                    pass
            if r_url:
                try:
                    self.redis_client = redis.Redis.from_url(r_url)
                except Exception:
                    self.redis_client = None

    # ------------------------------------------------------------------
    # Cache / billing (preserved from prior gateway)
    # ------------------------------------------------------------------

    def _get_cache_key(self, prompt, system_instruction, model, provider: str = ''):
        # Provider omitted from hash so legacy caches and callers remain valid;
        # model ids are globally unique across vendors in our catalog.
        raw_str = f"{prompt}||{system_instruction or ''}||{model}"
        return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

    def _check_cache(self, cache_key):
        if self.redis_client:
            try:
                cached_val = self.redis_client.get(f"ai_cache:{cache_key}")
                if cached_val:
                    return cached_val.decode('utf-8'), "redis_hit"
            except Exception:
                pass
        try:
            from app import db
            from sqlalchemy import text
            sql = text("SELECT response_text FROM ai_response_cache WHERE prompt_hash = :hash_val")
            result = db.session.execute(sql, {"hash_val": cache_key}).fetchone()
            if result:
                return result[0], "db_hit"
        except Exception:
            pass
        return None, "cache_miss"

    def _write_cache(self, cache_key, response_text, model):
        if self.redis_client:
            try:
                self.redis_client.setex(f"ai_cache:{cache_key}", 86400, response_text)
            except Exception:
                pass
        try:
            from app import db
            from app.models import AIResponseCache
            record = AIResponseCache.query.filter_by(prompt_hash=cache_key).first()
            if record:
                record.response_text = response_text
                record.model_used = model
            else:
                db.session.add(AIResponseCache(
                    prompt_hash=cache_key,
                    model_used=model,
                    response_text=response_text,
                ))
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    def _log_billing(self, user_id, model, input_tokens, output_tokens, provider: str = '',
                     latency_ms: int = 0, status: str = 'success', error: str = None,
                     organization_id=None, campaign_id=None, retry_count: int = 0):
        if not user_id:
            return
        cost = estimate_cost(model, input_tokens, output_tokens)
        try:
            from app import db
            from app.models import TokenBillingLog, UserRateLimit, AIRequestLog
            from datetime import datetime, timedelta

            db.session.add(TokenBillingLog(
                user_id=user_id,
                model_used=model[:50],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                calculated_cost=cost,
            ))

            limit = UserRateLimit.query.filter_by(user_id=user_id).first()
            if limit:
                limit.credits_used += (input_tokens + output_tokens)
            else:
                db.session.add(UserRateLimit(
                    user_id=user_id,
                    monthly_credits_limit=50000,
                    credits_used=input_tokens + output_tokens,
                    reset_date=datetime.utcnow() + timedelta(days=30),
                ))

            # Rich usage log (new table — best-effort)
            try:
                db.session.add(AIRequestLog(
                    user_id=user_id,
                    organization_id=organization_id,
                    campaign_id=campaign_id,
                    provider=provider or 'unknown',
                    model_used=(model or '')[:100],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    latency_ms=latency_ms,
                    calculated_cost=cost,
                    status=status,
                    error_message=(error or '')[:500] if error else None,
                    retry_count=retry_count,
                ))
            except Exception:
                pass

            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    def _check_rate_limit(self, user_id):
        if not user_id:
            return True
        try:
            from app import db
            from sqlalchemy import text
            row = db.session.execute(
                text("SELECT credits_used, monthly_credits_limit FROM user_rate_limits WHERE user_id = :user"),
                {"user": user_id},
            ).fetchone()
            if row and row[0] >= row[1]:
                return False
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt,
        system_instruction=None,
        model=None,
        user_id=None,
        skip_cache=False,
        provider=None,
        task_type=None,
        temperature=None,
        max_tokens=None,
        organization_id=None,
        campaign_id=None,
        **kwargs,
    ) -> Tuple[str, int]:
        """
        Legacy-compatible generate.

        Returns (text, total_tokens) — unchanged contract for GeminiService / routes.
        """
        response = self.execute(AIRequest(
            prompt=prompt,
            system_instruction=system_instruction,
            model=model,
            provider=self._coerce_provider(provider, model),
            task_type=self._coerce_task(task_type),
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            organization_id=organization_id,
            campaign_id=campaign_id,
            skip_cache=skip_cache,
            metadata=kwargs or {},
        ))
        return response.text, response.tokens

    def execute(self, request: AIRequest) -> AIResponse:
        """Full multi-provider execution with routing, retry, and fallback."""
        if not self._check_rate_limit(request.user_id):
            raise ValueError('Monthly credit limit exceeded. Please upgrade your subscription tier.')

        request = self.pipeline.preprocess(request)
        provider_id, model_id = self.router.select(request)
        request.model = model_id

        cache_key = self._get_cache_key(
            request.prompt, request.system_instruction, model_id, provider_id.value
        )
        if not request.skip_cache:
            cached_val, _hit = self._check_cache(cache_key)
            if cached_val:
                return AIResponse(
                    text=cached_val,
                    provider=provider_id.value,
                    model=model_id,
                    cached=True,
                    total_tokens=0,
                )

        errors = []
        attempts = [(provider_id, model_id)]
        for fb in self.router.fallback_chain(provider_id):
            from app.services.ai.catalog import resolve_default_model
            attempts.append((fb, resolve_default_model(fb)))

        last_error: Optional[Exception] = None
        for idx, (pid, mid) in enumerate(attempts):
            provider = self.registry.get(pid)
            if not provider or not provider.enabled:
                continue
            try:
                req = AIRequest(
                    prompt=request.prompt,
                    system_instruction=request.system_instruction,
                    task_type=request.task_type,
                    provider=pid,
                    model=mid,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=request.stream,
                    json_mode=request.json_mode,
                    timeout=request.timeout,
                    user_id=request.user_id,
                    organization_id=request.organization_id,
                    campaign_id=request.campaign_id,
                    skip_cache=True,
                    metadata=request.metadata,
                    images=request.images,
                    documents=request.documents,
                )
                result = provider.generate_text(req)
                result.text = self.pipeline.postprocess(result.text)
                result.fallback_used = idx > 0
                result.retry_count = idx

                self._log_billing(
                    request.user_id,
                    result.model,
                    result.input_tokens,
                    result.output_tokens,
                    provider=result.provider,
                    latency_ms=result.latency_ms,
                    organization_id=request.organization_id,
                    campaign_id=request.campaign_id,
                    retry_count=result.retry_count,
                )
                if not request.skip_cache:
                    self._write_cache(cache_key, result.text, result.model)
                return result
            except Exception as e:
                last_error = e
                errors.append(f'{pid.value}: {e}')
                try:
                    current_app.logger.warning('AI provider %s failed: %s', pid.value, e)
                except Exception:
                    pass
                continue

        # Never expose raw provider failures to end users
        try:
            current_app.logger.error('All AI providers failed: %s', ' | '.join(errors))
        except Exception:
            pass
        raise RuntimeError(
            'AI generation is temporarily unavailable. Please try again in a moment.'
        ) from last_error

    def stream(self, request: AIRequest) -> Generator[str, None, None]:
        request = self.pipeline.preprocess(request)
        provider_id, model_id = self.router.select(request)
        provider = self.registry.get(provider_id)
        if not provider:
            raise RuntimeError('No AI provider available.')
        request.model = model_id
        request.provider = provider_id
        for chunk in provider.stream(request):
            yield chunk

    def list_providers(self) -> list:
        return self.registry.list_providers()

    def list_models(self) -> list:
        return [
            {
                'id': m.model_id,
                'name': m.display_name,
                'provider': m.provider.value,
                'supports_stream': m.supports_stream,
                'supports_vision': m.supports_vision,
            }
            for m in self.registry.list_models()
        ]

    def ui_provider_options(self) -> list:
        return self.registry.ui_options()

    @staticmethod
    def _coerce_provider(provider, model) -> Optional[ProviderId]:
        if provider is None or provider == '' or str(provider).lower() == 'auto':
            inferred = infer_provider_from_model(model) if model else None
            return inferred or ProviderId.AUTO
        if isinstance(provider, ProviderId):
            return provider
        try:
            return ProviderId(str(provider).lower())
        except ValueError:
            return ProviderId.AUTO

    @staticmethod
    def _coerce_task(task_type) -> TaskType:
        if task_type is None:
            return TaskType.UNKNOWN
        if isinstance(task_type, TaskType):
            return task_type
        try:
            return TaskType(str(task_type).lower())
        except ValueError:
            return TaskType.UNKNOWN
