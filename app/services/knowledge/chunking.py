"""Intelligent text chunking for RAG."""
from __future__ import annotations

import re
from typing import Dict, List


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
) -> List[Dict]:
    """
    Split text into overlapping chunks preferring paragraph/sentence boundaries.
    Returns list of {index, content, token_estimate, meta}.
    """
    text = (text or '').strip()
    if not text:
        return []

    paragraphs = re.split(r'\n\s*\n', text)
    units: List[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            units.append(para)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            buf = ''
            for sent in sentences:
                if len(buf) + len(sent) + 1 <= chunk_size:
                    buf = f'{buf} {sent}'.strip()
                else:
                    if buf:
                        units.append(buf)
                    if len(sent) > chunk_size:
                        for i in range(0, len(sent), chunk_size - overlap):
                            units.append(sent[i:i + chunk_size])
                        buf = ''
                    else:
                        buf = sent
            if buf:
                units.append(buf)

    chunks: List[Dict] = []
    i = 0
    while i < len(units):
        parts = [units[i]]
        length = len(units[i])
        j = i + 1
        while j < len(units) and length + len(units[j]) + 2 <= chunk_size:
            parts.append(units[j])
            length += len(units[j]) + 2
            j += 1
        content = '\n\n'.join(parts).strip()
        chunks.append({
            'index': len(chunks),
            'content': content,
            'token_estimate': estimate_tokens(content),
            'meta': {'unit_start': i, 'unit_end': j - 1},
        })
        if j >= len(units):
            break
        # overlap: step back if needed
        step = max(1, j - i - (1 if overlap > 0 else 0))
        i += step

    return chunks
