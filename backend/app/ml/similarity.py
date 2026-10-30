"""How alike two reports read. TF-IDF over words and character pieces, then cosine similarity.

It only ever runs on a handful of candidates the caller has already narrowed down by category,
building and time, so it stays fast and needs no model download.
"""

import math
from collections import Counter

from app.ml.text import cosine, similarity_features, weight


def rank(query: str, candidates: list[tuple[str, str]]) -> list[tuple[str, float]]:
    """candidates are (id, text). Returns (id, score) best first, scores from 0 to 1."""
    if not candidates:
        return []
    documents = [similarity_features(text) for _, text in candidates]
    query_features = similarity_features(query)
    frequency: Counter[str] = Counter()
    for features in [*documents, query_features]:
        frequency.update(features.keys())
    total = len(documents) + 1
    idf = {feature: math.log((1 + total) / (1 + count)) + 1.0 for feature, count in frequency.items()}
    default = math.log(1 + total) + 1.0
    query_vector = weight(query_features, idf, default)
    scored = [(ident, cosine(query_vector, weight(features, idf, default))) for (ident, _), features in zip(candidates, documents, strict=True)]
    return sorted(scored, key=lambda item: item[1], reverse=True)
