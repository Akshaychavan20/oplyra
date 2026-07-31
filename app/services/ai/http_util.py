"""HTTP helpers shared by OpenAI-compatible and Anthropic providers."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

import requests


class ProviderHTTPError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float = 60.0,
    max_retries: int = 3,
) -> Tuple[Dict[str, Any], int]:
    """POST JSON with exponential backoff on 429/5xx. Returns (body, latency_ms)."""
    delay = 1.0
    last_err: Optional[Exception] = None
    started = time.time()

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = int((time.time() - started) * 1000)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 400:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:500]
                raise ProviderHTTPError(
                    f'HTTP {resp.status_code}: {detail}',
                    status_code=resp.status_code,
                    retryable=resp.status_code in (429, 500, 502, 503, 504),
                )
            return resp.json(), latency_ms
        except ProviderHTTPError:
            raise
        except requests.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise ProviderHTTPError(str(e), retryable=True) from e

    raise ProviderHTTPError(str(last_err or 'Request failed'), retryable=True)


def mock_response_text(provider: str, model: str, prompt: str) -> str:
    topic = (prompt or '')[:80].replace('\n', ' ')
    return (
        f'[MOCK GENERATION: {provider}/{model}]\n'
        f'Generated marketing copy for: {topic}'
    )


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))
