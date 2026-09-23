# Review intelligence model card

This project uses a real, saved TF-IDF + logistic-regression classifier and SHAP explanations. The training labels are **original review (OR)** and **computer-generated review (CG)**. The application presents the latter as “Fake / Suspicious” for screening, but neither class proves whether a purchase or statement is genuine. Treat decisions as moderation assistance.

## Trained model

| Item | Value |
| --- | --- |
| Input | English review text, maximum 5,000 characters in the API |
| Representation | Lowercase TF-IDF, unigrams and bigrams, sublinear term frequency |
| Vocabulary | 30,000 features, minimum document frequency 2 |
| Classifier | scikit-learn LogisticRegression, random state 42, max iterations 1,000 |
| Output | Probabilities for class 0 (OR) and class 1 (CG), threshold 0.5 |
| Original dataset | 40,432 rows: 20,216 OR and 20,216 CG |
| Original split | Stratified 80% training / 20% test, random state 42 |
| Explanation | SHAP LinearExplainer, interventional semantics, 200 saved training examples |
| Artifact version | `tfidf-lr-b3c72b593a92` |

The existing dataset is `ai_model/dataset/fake_reviews.csv`; its external source and redistribution license have not been independently verified. No claim of a verified fraud dataset is made. The saved classifier, vectorizer and background are preserved from the original project.

## Measured evaluation

Run from the project root:

```powershell
.\venv\Scripts\python.exe -m ai_model.evaluate_model
```

The evaluator reconstructs the original training script's seed-42 split. It verifies that the saved vocabulary matches and the IDF values and SHAP background agree with the reconstructed training rows within `1e-12`. The observed maximum background difference was `1.39e-16`, a floating-point normalization difference. This supports the reconstructed split but is not a signed record of the model's historical training.

The dataset contains **27 duplicate normalized text rows**. **10 held-out rows** also occur in training and were excluded from the reported metrics. The resulting evaluation uses **8,077 reviews**; the training partition has **32,345 reviews**. The full original split metrics are separately retained in the JSON report for auditability.

| Metric | Result |
| --- | ---: |
| Accuracy | 93.85% |
| Precision, CG class | 95.06% |
| Recall, CG class | 92.49% |
| F1, CG class | 93.75% |
| ROC AUC | 0.9847 |

Confusion matrix, rows = actual and columns = predicted:

| | Predicted OR | Predicted CG |
| --- | ---: | ---: |
| Actual OR | 3,850 | 194 |
| Actual CG | 303 | 3,730 |

These are **internal reconstructed holdout results**, not independently collected real-world fraud accuracy. Paraphrases and shared products/authors can still create dependency between partitions. There is no product-group holdout, prospective study, probability calibration study or multilingual validation. Full metrics, checks, artifact hashes and limitations are in `saved_model/evaluation_metrics.json`. `/model-info` exposes that report only while the model and vectorizer hashes match it.

## How SHAP explains a prediction

For this binary linear classifier, SHAP explains the log-odds of class 1:

```text
base value + sum(all feature SHAP values) = class-1 log-odds
class-1 probability = 1 / (1 + exp(-log-odds))
```

Positive contributions push toward CG; negative contributions push toward OR. The UI shows up to 12 present words/phrases. Omitted and absent vocabulary features can also contribute relative to the background. Therefore the API includes `other_contributions`, the full sum and `additivity_error`; the displayed words alone must not be presented as the full decomposition. A mathematical additivity test checks the actual saved model.

These are model attributions, not causal evidence of deception. See [SHAP LinearExplainer documentation](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html) and [scikit-learn LogisticRegression documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).

## Additional analysis and context

Sentiment and product aspects are **English rule-based baselines**, using opinion words, clause boundaries, nearest aspect mentions and local negation. They are not trained sentiment models. Mixed statements such as “sound is amazing but battery is average” can produce different aspect labels. Sarcasm, uncommon phrases and implicit aspects can fail.

The **authenticity score is a heuristic score**, separate from the trained classifier:

```text
authenticity = clip(raw OR probability in percent + context adjustments, 0, 100)
```

| Context signal | Adjustment in percentage points |
| --- | ---: |
| Matching customer order exists | +8 |
| Purchase not verified | 0 |
| Same normalized review text appears elsewhere | -min(25, 10 + 5 × duplicate count) |
| At least 5 previous reviews in the last 24 hours | -min(15, recent review count) |
| Product identity and total customer review count | 0; recorded as context |

These weights are hand-selected demonstration rules, not statistically fitted fraud estimates. A matching order establishes a recorded purchase, not honesty. Lack of a matching order is not penalized. Context **never changes the trained text prediction, probability or SHAP explanation**. Every adjustment appears in `context_signals`. A text-only analysis applies no contextual adjustment.

If no vocabulary features match, the API labels the evidence insufficient, returns an empty word explanation, and discloses that the probability is only the classifier's intercept prior. Such a result should not be used for moderation.

## Reproducible future training

```powershell
.\venv\Scripts\python.exe -m ai_model.train_model --output-dir ai_model/experiment_model
```

The improved training pipeline normalizes text for deduplication, removes conflicting-label text groups, deduplicates before splitting, fits TF-IDF only on the training partition, saves model/TF-IDF/background, and writes evaluation metrics plus hashed train/test membership. Existing artifact files are protected unless `--overwrite` is explicitly used. A newly trained experiment has its own metrics; the shipped-model evaluation script specifically audits the original split.

Use only trusted local pickle/joblib artifacts; the application accepts no uploaded model artifacts. Model updates should be reviewed and re-evaluated before replacing the submission's artifacts.

## Suitable resume statement

“Built a full-stack product review intelligence system with TF-IDF/logistic-regression classification, SHAP feature explanations, purchase verification, contextual review screening and moderation analytics; measured 93.85% accuracy on an audited internal holdout of 8,077 original/computer-generated reviews.”

Avoid claiming that the model proves fraud, uses a trained multimodal/contextual model, or achieves that accuracy on real customer fraud.
