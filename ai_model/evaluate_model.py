"""Audit the shipped model against the original script's reconstructable split.

Does not train or replace model artifacts. Verifies the saved vocabulary, IDF and
SHAP background against the original seed-42 training partition before reporting.
Metrics exclude test texts also present in training; the full legacy result is
retained separately for transparency. This is not external validation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.model_selection import train_test_split

try:
    from ai_model.train_model import BASE_DIR, SEED, compute_metrics, load_dataset, normalized_text, sha256
except ModuleNotFoundError:
    from train_model import BASE_DIR, SEED, compute_metrics, load_dataset, normalized_text, sha256


def evaluate(data_path: Path, model_dir: Path) -> dict:
    data = load_dataset(data_path)
    train_frame, test_frame = train_test_split(data, test_size=0.2, random_state=SEED, stratify=data["label"])
    model = joblib.load(model_dir / "fake_review_model.pkl")
    vectorizer = joblib.load(model_dir / "tfidf_vectorizer.pkl")
    background = joblib.load(model_dir / "shap_background.pkl")
    reconstructed_vectorizer = clone(vectorizer)
    reconstructed_vectorizer.fit_transform(train_frame["text_"])
    vocabulary_matches = reconstructed_vectorizer.vocabulary_ == vectorizer.vocabulary_
    idf_matches = vocabulary_matches and bool(np.allclose(reconstructed_vectorizer.idf_, vectorizer.idf_, rtol=0, atol=1e-12))
    reconstructed_background = vectorizer.transform(train_frame["text_"].iloc[:background.shape[0]])
    background_delta = background - reconstructed_background
    background_max_error = float(np.max(np.abs(background_delta.data))) if background_delta.nnz else 0.0
    # fit_transform and transform normalize in a different sparse-index order.
    # Equivalent values can therefore differ by machine precision (~1e-16).
    background_matches = background.shape == reconstructed_background.shape and background_max_error < 1e-12
    checks = {"vocabulary_matches_reconstructed_training": vocabulary_matches, "idf_matches_reconstructed_training": idf_matches, "shap_background_matches_training_prefix": bool(background_matches)}
    if not all(checks.values()):
        raise RuntimeError("Saved artifacts do not verify against the legacy split. Refusing to publish purported holdout metrics: " + json.dumps(checks))
    normalized_train = set(train_frame["text_"].map(normalized_text))
    normalized_test = test_frame["text_"].map(normalized_text)
    overlap_mask = normalized_test.isin(normalized_train)
    evaluation_frame = test_frame.loc[~overlap_mask].copy()
    evaluation_frame["normalized_text"] = evaluation_frame["text_"].map(normalized_text)
    before_dedup = len(evaluation_frame)
    evaluation_frame = evaluation_frame.drop_duplicates("normalized_text")
    vectors = vectorizer.transform(evaluation_frame["text_"])
    fake_index = list(model.classes_).index(1)
    report = compute_metrics(evaluation_frame["label"].to_numpy(), model.predict(vectors), model.predict_proba(vectors)[:, fake_index])
    full_vectors = vectorizer.transform(test_frame["text_"])
    normalized_all = data["text_"].map(normalized_text)
    report.update({
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "Reconstructed original seed-42 stratified 80/20 split; excluded held-out text overlapping training and deduplicated the remaining holdout. No artifacts retrained.",
        "provenance_status": "Saved vocabulary matches and IDF/SHAP background match the reconstructed training partition within 1e-12 numerical tolerance; the original model has no signed training manifest.",
        "seed": SEED,
        "train_size": len(train_frame),
        "original_test_size": len(test_frame),
        "dataset_rows": len(data),
        "dataset_sha256": sha256(data_path),
        "model_sha256": sha256(model_dir / "fake_review_model.pkl"),
        "vectorizer_sha256": sha256(model_dir / "tfidf_vectorizer.pkl"),
        "sklearn_version": sklearn.__version__,
        "artifact_verification": checks,
        "background_max_absolute_error": background_max_error,
        "audit": {"normalized_duplicate_rows_in_dataset": int(normalized_all.duplicated().sum()), "test_rows_overlapping_training_excluded": int(overlap_mask.sum()), "repeated_test_rows_excluded": before_dedup - len(evaluation_frame)},
        "train_test_text_overlap": 0,
        "legacy_split_metrics": compute_metrics(test_frame["label"].to_numpy(), model.predict(full_vectors), model.predict_proba(full_vectors)[:, fake_index]),
        "limitations": ["This is a reconstructed internal holdout, not an independently collected external test set.", "Original training provenance has no persisted split manifest; checks establish matching preprocessing and background, not a proof of every historical training operation.", "Normalized duplicate removal does not detect paraphrases or related customer/product leakage.", "Labels mean original versus computer-generated text, not confirmed fraudulent purchases.", "No independent probability calibration. Dataset external source and license are unverified."],
    })
    (model_dir / "evaluation_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=BASE_DIR / "dataset" / "fake_reviews.csv")
    parser.add_argument("--model-dir", type=Path, default=BASE_DIR / "saved_model")
    args = parser.parse_args()
    report = evaluate(args.data, args.model_dir)
    print(json.dumps({key: report[key] for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "test_size", "artifact_verification", "audit")}, indent=2))
    print(f"Report: {args.model_dir / 'evaluation_metrics.json'}")


if __name__ == "__main__":
    main()
