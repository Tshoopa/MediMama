# backend/rag/sparse_utils.py
"""Shared sparse (keyword) vector builder.

Used by both the ingestor (index time) and the retriever (query time).
These two MUST stay identical — any divergence silently breaks keyword recall.
"""

import hashlib
import math
import re
from collections import Counter

from qdrant_client.models import SparseVector

# Conservative on purpose — only the most frequent English stopwords.
ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "so", "of", "to", "in",
    "on", "at", "for", "with", "without", "is", "are", "was", "were",
    "be", "been", "being", "he", "she", "it", "they", "his", "her",
    "him", "them", "their", "i", "you", "your", "my", "me", "we", "us",
    "our", "this", "that", "these", "those", "as", "by", "from", "than",
    "then", "there", "here", "up", "down", "out", "over", "under",
    "again", "further", "not", "no", "do", "does", "did", "doing",
    "has", "have", "had", "having", "will", "would", "can", "could",
    "should", "shall", "may", "might", "must", "into", "about", "after",
    "before", "during", "while", "some", "any", "all", "both", "each",
    "few", "more", "most", "other", "such", "only", "own", "same", "just",
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in tokens if t not in ENGLISH_STOPWORDS and len(t) > 1]


def _hash_token(token: str, sparse_dim: int) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % sparse_dim


def build_sparse_vector(text: str, sparse_dim: int) -> SparseVector:
    tokens = tokenize(text)
    if not tokens:
        return SparseVector(indices=[], values=[])

    bucket: dict[int, float] = {}
    for token, tf in Counter(tokens).items():
        idx = _hash_token(token, sparse_dim)
        # log-scaled tf so a single repeated word can't dominate the vector
        bucket[idx] = bucket.get(idx, 0.0) + (1.0 + math.log(tf))

    return SparseVector(indices=list(bucket.keys()), values=list(bucket.values()))