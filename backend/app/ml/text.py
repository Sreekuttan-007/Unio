"""Text handling shared by the classifier and the similarity scorer. Plain Python, no native code."""

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z]+|\d+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def classifier_features(text: str) -> Counter[str]:
    """Words, word pairs and character pieces. The character pieces keep typos readable."""
    words = ["#" if token.isdigit() else token for token in tokens(text)]
    features: Counter[str] = Counter()
    for word in words:
        features[f"w:{word}"] += 1
    for first, second in zip(words, words[1:], strict=False):
        features[f"b:{first} {second}"] += 1
    for word in words:
        if len(word) < 4 or word == "#":
            continue
        padded = f"<{word}>"
        for size in (3, 4):
            for start in range(len(padded) - size + 1):
                features[f"c:{padded[start : start + size]}"] += 1
    return features


def similarity_features(text: str) -> Counter[str]:
    """Like classifier_features but keeps the digits, so ARB-204 and ARB-205 stay different."""
    features: Counter[str] = Counter()
    toks = tokens(text)
    for token in toks:
        features[f"w:{token}"] += 2
        if len(token) >= 4 and not token.isdigit():
            padded = f"<{token}>"
            for start in range(len(padded) - 2):
                features[f"c:{padded[start : start + 3]}"] += 1
    return features


def weight(counts: Counter[str], idf: dict[str, float], default_idf: float) -> dict[str, float]:
    """Sublinear TF-IDF, scaled to unit length."""
    vector = {feature: (1.0 + math.log(count)) * idf.get(feature, default_idf) for feature, count in counts.items()}
    norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {feature: value / norm for feature, value in vector.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(feature, 0.0) for feature, value in left.items())
