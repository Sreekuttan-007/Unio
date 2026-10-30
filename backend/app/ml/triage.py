"""Category and urgency for a report.

Category comes from a small trained model (TF-IDF into naive Bayes, written in plain Python) with a
keyword rule set behind it. Urgency is rules only, with a safety floor that can raise it and never
lower it. Neither one decides a priority: a policy table does that, from these as inputs.
"""

import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.ml.text import classifier_features, weight

ARTIFACT = Path(__file__).resolve().parent / "artifacts" / "v1" / "triage.json.gz"
CATEGORIES = ("ELECTRICAL", "NETWORK", "PLUMBING", "HVAC", "CARPENTRY", "EQUIPMENT", "HOUSEKEEPING", "SAFETY", "OTHER")
SCALE = 24.0  # turns unit-length document vectors into usable log-likelihood differences


class TriageModel:
    def __init__(self, version: str, classes: list[str], idf: dict[str, float], default_idf: float, log_prior: dict[str, float],
                 log_prob: dict[str, dict[str, float]], unseen: dict[str, float], temperature: float) -> None:
        self.version = version
        self.classes = classes
        self.idf = idf
        self.default_idf = default_idf
        self.log_prior = log_prior
        self.log_prob = log_prob
        self.unseen = unseen
        self.temperature = temperature

    def scores(self, text: str) -> dict[str, float]:
        vector = weight(classifier_features(text), self.idf, self.default_idf)
        return {
            label: self.log_prior[label] + SCALE * sum(value * self.log_prob[label].get(feature, self.unseen[label]) for feature, value in vector.items())
            for label in self.classes
        }

    def predict(self, text: str) -> tuple[str, float]:
        scores = self.scores(text)
        top = max(scores.values())
        exps = {label: math.exp((score - top) / self.temperature) for label, score in scores.items()}
        total = sum(exps.values())
        best = max(exps, key=lambda label: exps[label])
        return best, exps[best] / total

    # ---- training ---------------------------------------------------------------------------

    @classmethod
    def train(cls, rows: list[tuple[str, str]], version: str, min_df: int = 2, alpha: float = 0.05) -> "TriageModel":
        documents = [(classifier_features(text), label) for text, label in rows]
        frequency: Counter[str] = Counter()
        for counts, _ in documents:
            frequency.update(counts.keys())
        keep = {feature for feature, count in frequency.items() if count >= min_df}
        total_docs = len(documents)
        idf = {feature: math.log((1 + total_docs) / (1 + frequency[feature])) + 1.0 for feature in keep}
        default_idf = math.log(1 + total_docs) + 1.0

        mass: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        class_docs: Counter[str] = Counter()
        for counts, label in documents:
            class_docs[label] += 1
            for feature, value in weight(Counter({k: v for k, v in counts.items() if k in keep}), idf, default_idf).items():
                mass[label][feature] += value
        classes = [label for label in CATEGORIES if class_docs[label]]
        vocabulary = len(keep)
        log_prob: dict[str, dict[str, float]] = {}
        unseen: dict[str, float] = {}
        for label in classes:
            total = sum(mass[label].values()) + alpha * vocabulary
            log_prob[label] = {feature: math.log((value + alpha) / total) for feature, value in mass[label].items()}
            unseen[label] = math.log(alpha / total)
        log_prior = {label: math.log(class_docs[label] / total_docs) for label in classes}
        return cls(version, classes, idf, default_idf, log_prior, log_prob, unseen, temperature=1.0)

    def fit_temperature(self, validation: list[tuple[str, str]]) -> float:
        """Picks the temperature that gives the best-calibrated confidence on data it was not trained on."""
        best, best_loss = 1.0, float("inf")
        scored = [(self.scores(text), label) for text, label in validation]
        for step in range(1, 61):
            temperature = step * 0.5
            loss = 0.0
            for scores, label in scored:
                top = max(scores.values())
                exps = {name: math.exp((score - top) / temperature) for name, score in scores.items()}
                loss -= math.log(max(exps.get(label, 0.0) / sum(exps.values()), 1e-9))
            if loss < best_loss:
                best, best_loss = temperature, loss
        self.temperature = best
        return best

    # ---- storage ----------------------------------------------------------------------------

    def save(self, path: Path = ARTIFACT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "classes": self.classes,
            "idf": {k: round(v, 4) for k, v in self.idf.items()},
            "defaultIdf": self.default_idf,
            "logPrior": self.log_prior,
            "logProb": {label: {k: round(v, 4) for k, v in table.items()} for label, table in self.log_prob.items()},
            "unseen": self.unseen,
            "temperature": self.temperature,
        }
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))

    @classmethod
    def load(cls, path: Path = ARTIFACT) -> "TriageModel | None":
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(data["version"], data["classes"], data["idf"], data["defaultIdf"], data["logPrior"], data["logProb"], data["unseen"], data["temperature"])


# ---- keyword rules: the fallback when the model is off or missing ---------------------------

KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SAFETY", ("smoke", "burning", "burnt smell", "fire", "spark", "gas smell", "exposed wire", "live wire", "shock", "short circuit", "unsafe", "chemical spill", "stuck in the lift", "emergency exit")),
    ("NETWORK", ("wifi", "wi-fi", "internet", "network", "lan ", "ethernet", "router", "access point", "connectivity", "browse")),
    ("PLUMBING", ("leak", "tap ", "tap is", "water", "drain", "flush", "toilet", "pipe", "washbasin", "sewage", "urinal", "geyser", "flooded")),
    ("HVAC", ("air conditioner", "air-conditioner", " ac ", "ac is", "ac in", "cooling", "ventilation", "exhaust fan", "thermostat", "compressor")),
    ("EQUIPMENT", ("projector", "hdmi", "microphone", " mic ", "speaker", "smart board", "smartboard", "podium", "printer", "display", "clicker", "visualiser", "monitor")),
    ("ELECTRICAL", ("power", "electric", "light", "socket", "switch board", "switchboard", "mcb", "tripped", "fan ", "current", "bulb", "plug", "tube")),
    ("CARPENTRY", ("door", "hinge", "bench", "desk", "window", "chair", "cupboard", "lock", "shelf", "whiteboard", "drawer", "handle", "partition")),
    ("HOUSEKEEPING", ("dirty", "clean", "dustbin", "garbage", "sweep", "litter", "dust", "mop", "soap", "smells bad", "pest", "mosquito")),
)

CRITICAL_WORDS = ("smoke", "fire", "spark", "burning", "gas smell", "exposed wire", "live wire", "shock", "flood", "collapse", "stuck in the lift", "chemical spill", "short circuit")
HIGH_WORDS = ("not working", "no power", "no electricity", "no internet", "power cut", "went off", "tripped", "down", "burst", "overflow", "blocked", "urgent", "emergency", "asap", "exam", "broken", "stopped", "dead")
LOW_WORDS = ("minor", "whenever", "no rush", "cosmetic", "suggestion", "when possible", "not urgent")


def rule_category(text: str) -> tuple[str, float]:
    lower = f" {text.lower()} "
    for category, words in KEYWORDS:
        if any(word in lower for word in words):
            return category, 0.9
    return "OTHER", 0.4


def urgency(text: str, category: str) -> str:
    """Rules only. Safety words set a floor that nothing else can lower."""
    lower = text.lower()
    if any(word in lower for word in CRITICAL_WORDS):
        return "CRITICAL"
    if category == "SAFETY":
        return "HIGH"
    if any(word in lower for word in LOW_WORDS):
        return "LOW"
    if any(word in lower for word in HIGH_WORDS):
        return "HIGH"
    return "LOW" if category in ("HOUSEKEEPING", "OTHER") else "MEDIUM"


# Rules that are specific enough to correct the model when it is unsure. The broad ones (electrical,
# carpentry, housekeeping) are not here, because plenty of unrelated sentences contain those words.
SPECIFIC_RULES = frozenset({"HVAC", "SAFETY", "NETWORK", "PLUMBING", "EQUIPMENT"})
OVERRIDE_BELOW = 0.9


def classify(text: str, model: TriageModel | None) -> tuple[str, float, str, str]:
    """(category, confidence, source, model version).

    The model answers, and a specific keyword rule overrides it only when the model is unsure.
    """
    rule_label, rule_confidence = rule_category(text)
    if model is None:
        return rule_label, rule_confidence, "RULE", "rules-1"
    label, confidence = model.predict(text)
    if rule_label in SPECIFIC_RULES and rule_label != label and confidence < OVERRIDE_BELOW:
        return rule_label, 0.8, "RULE", "rules-1"
    if label == "OTHER" and rule_label != "OTHER":
        return rule_label, 0.7, "RULE", "rules-1"
    return label, confidence, "ML", model.version


def describe(model: TriageModel | None) -> dict[str, Any]:
    return {"loaded": model is not None, "version": model.version if model else None}
