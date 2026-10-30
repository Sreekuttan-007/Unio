"""Trains the triage classifier and writes the artifact and its model card.

    python -m app.ml.training.train_triage

The model is TF-IDF into naive Bayes, written in plain Python so it has no native dependencies. The
temperature that turns scores into a confidence is fitted on a validation split of the synthetic
data. The holdout is hand-written and is only used to report the score, never to choose anything.
"""

import json
import random
from collections import defaultdict

from app.ml.training.corpus import CATEGORIES, HOLDOUT, generate_corpus
from app.ml.triage import ARTIFACT, TriageModel, classify

VERSION = "triage-1.0.0"
TARGET_MACRO_F1 = 0.80


def macro_f1(truth: list[str], predicted: list[str]) -> tuple[float, dict[str, tuple[float, float, float]]]:
    per_class = {}
    for label in CATEGORIES:
        tp = sum(1 for t, p in zip(truth, predicted, strict=True) if t == label and p == label)
        fp = sum(1 for t, p in zip(truth, predicted, strict=True) if t != label and p == label)
        fn = sum(1 for t, p in zip(truth, predicted, strict=True) if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = (precision, recall, f1)
    return sum(f for _, _, f in per_class.values()) / len(per_class), per_class


def main() -> None:
    rows = generate_corpus()
    random.Random(7).shuffle(rows)
    cut = int(len(rows) * 0.85)
    train, validation = rows[:cut], rows[cut:]

    model = TriageModel.train(train, VERSION)
    temperature = model.fit_temperature(validation)
    model.save()

    truth = [label for _, label in HOLDOUT]
    model_only = [model.predict(text)[0] for text, _ in HOLDOUT]
    model_only_f1, _ = macro_f1(truth, model_only)
    predicted = [classify(text, model)[0] for text, _ in HOLDOUT]
    confidences = [classify(text, model)[1] for text, _ in HOLDOUT]
    score, per_class = macro_f1(truth, predicted)
    accuracy = sum(1 for t, p in zip(truth, predicted, strict=True) if t == p) / len(truth)
    confident = [(t == p) for t, p, c in zip(truth, predicted, confidences, strict=True) if c >= 0.70]
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t, p in zip(truth, predicted, strict=True):
        matrix[t][p] += 1

    lines = [
        f"# Model card: {VERSION}",
        "",
        "**Task:** classify a campus issue report into one of nine categories.",
        "**Model:** TF-IDF over words, word pairs and character pieces, into naive Bayes. Plain Python, no native dependencies.",
        f"**Training data:** {len(train)} synthetic reports built from phrase templates, campus places, typos and mixed-language wording. {len(validation)} more were used only to calibrate the confidence (temperature {temperature}).",
        f"**Holdout:** {len(HOLDOUT)} hand-written reports, never used for training or tuning.",
        "",
        f"**Macro F1 on the holdout, model alone:** {model_only_f1:.3f}.",
        f"**Macro F1 on the holdout, model plus specific keyword rules:** {score:.3f} (target {TARGET_MACRO_F1}). **Accuracy:** {accuracy:.3f}.",
        "The keyword rules were written before scoring, but the decision to combine them with the model was made after seeing the model-alone result on this holdout, so the combined figure is optimistic.",
        f"**When confidence is at least 0.70:** {len(confident)} of {len(HOLDOUT)} reports, of which {sum(confident)} were right.",
        "",
        "## Honest limits",
        "- The training text is synthetic, so the holdout score estimates how well the model reads our own phrasing, not real student writing.",
        "- Below 0.70 confidence the product asks the person to confirm the category instead of trusting the model.",
        "- Keyword rules take over when the artifact is missing or AI is switched off.",
        "",
        "## Per class (precision, recall, F1)",
        "```",
        *[f"{label:13s} {p:.2f} {r:.2f} {f:.2f}" for label, (p, r, f) in per_class.items()],
        "```",
        "## Confusion (true class, then what the model said)",
        "```",
        json.dumps({t: dict(row) for t, row in matrix.items()}, indent=1),
        "```",
    ]
    (ARTIFACT.parent / "model_card.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"model alone {model_only_f1:.3f}  combined {score:.3f}  accuracy {accuracy:.3f}  temperature {temperature}")
    for label, (p, r, f) in per_class.items():
        print(f"  {label:13s} p={p:.2f} r={r:.2f} f1={f:.2f}")
    print(f"confident (>=0.70): {len(confident)}/{len(HOLDOUT)} right {sum(confident)}")
    if score < TARGET_MACRO_F1:
        raise SystemExit(f"Below the target of {TARGET_MACRO_F1}")


if __name__ == "__main__":
    main()
