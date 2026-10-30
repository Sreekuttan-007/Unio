# Model card: triage-1.0.0

**Task:** classify a campus issue report into one of nine categories.
**Model:** TF-IDF over words, word pairs and character pieces, into naive Bayes. Plain Python, no native dependencies.
**Training data:** 2547 synthetic reports built from phrase templates, campus places, typos and mixed-language wording. 450 more were used only to calibrate the confidence (temperature 10.0).
**Holdout:** 90 hand-written reports, never used for training or tuning.

**Macro F1 on the holdout, model alone:** 0.862.
**Macro F1 on the holdout, model plus specific keyword rules:** 0.911 (target 0.8). **Accuracy:** 0.911.
The keyword rules were written before scoring, but the decision to combine them with the model was made after seeing the model-alone result on this holdout, so the combined figure is optimistic.
**When confidence is at least 0.70:** 87 of 90 reports, of which 80 were right.

## Honest limits
- The training text is synthetic, so the holdout score estimates how well the model reads our own phrasing, not real student writing.
- Below 0.70 confidence the product asks the person to confirm the category instead of trusting the model.
- Keyword rules take over when the artifact is missing or AI is switched off.

## Per class (precision, recall, F1)
```
ELECTRICAL    0.90 0.90 0.90
NETWORK       1.00 0.90 0.95
PLUMBING      0.91 1.00 0.95
HVAC          0.78 0.70 0.74
CARPENTRY     1.00 1.00 1.00
EQUIPMENT     0.75 0.90 0.82
HOUSEKEEPING  1.00 0.90 0.95
SAFETY        1.00 0.90 0.95
OTHER         0.91 1.00 0.95
```
## Confusion (true class, then what the model said)
```
{
 "ELECTRICAL": {
  "ELECTRICAL": 9,
  "EQUIPMENT": 1
 },
 "NETWORK": {
  "NETWORK": 9,
  "HVAC": 1
 },
 "PLUMBING": {
  "PLUMBING": 10
 },
 "HVAC": {
  "HVAC": 7,
  "PLUMBING": 1,
  "EQUIPMENT": 2
 },
 "CARPENTRY": {
  "CARPENTRY": 10
 },
 "EQUIPMENT": {
  "EQUIPMENT": 9,
  "HVAC": 1
 },
 "HOUSEKEEPING": {
  "HOUSEKEEPING": 9,
  "OTHER": 1
 },
 "SAFETY": {
  "SAFETY": 9,
  "ELECTRICAL": 1
 },
 "OTHER": {
  "OTHER": 10
 }
}
```
