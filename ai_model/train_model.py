"""Reproducible training with duplicate removal BEFORE the held-out split.

Usage: python -m ai_model.train_model --output-dir ai_model/experiment_model
The shipped artifacts are preserved unless --overwrite is explicitly supplied.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unicodedata

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent
SEED = 42


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = {"text_", "label"} - set(frame.columns)
    if missing:
        raise ValueError("Missing dataset columns: " + ", ".join(sorted(missing)))
    frame = frame[["text_", "label"]].dropna().copy()
    frame["text_"] = frame["text_"].astype(str)
    frame["label"] = frame["label"].map({"CG": 1, "OR": 0})
    frame = frame.dropna().copy()
    frame["label"] = frame["label"].astype(int)
    return frame


def prepare_dataset(path: Path) -> tuple[pd.DataFrame, dict]:
    frame = load_dataset(path)
    original_count = len(frame)
    frame["normalized_text"] = frame["text_"].map(normalized_text)
    empty = int((frame["normalized_text"] == "").sum())
    frame = frame[frame["normalized_text"] != ""].copy()
    label_counts = frame.groupby("normalized_text")["label"].nunique()
    conflicts = set(label_counts[label_counts > 1].index)
    conflict_rows = int(frame["normalized_text"].isin(conflicts).sum())
    frame = frame[~frame["normalized_text"].isin(conflicts)].copy()
    before = len(frame)
    frame = frame.drop_duplicates("normalized_text").reset_index(drop=True)
    if frame["label"].nunique() != 2 or frame["label"].value_counts().min() < 5:
        raise ValueError("Dataset needs at least five clean reviews in each class.")
    return frame, {
        "input_valid_rows": original_count,
        "empty_rows_removed": empty,
        "conflicting_label_groups_removed": len(conflicts),
        "conflicting_rows_removed": conflict_rows,
        "duplicate_rows_removed": before - len(frame),
        "clean_rows": len(frame),
    }


def compute_metrics(labels, predictions, probabilities) -> dict:
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(set(labels)) == 2 else None,
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
        "confusion_matrix_labels": ["Original (OR)", "Computer-generated (CG)"],
        "classification_report": classification_report(labels, predictions, labels=[0, 1], target_names=["Original (OR)", "Computer-generated (CG)"], output_dict=True, zero_division=0),
        "test_size": len(labels),
        "positive_class": "Computer-generated (CG), label 1",
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(data_path: Path, output_dir: Path, overwrite: bool = False) -> dict:
    artifact_names = ("fake_review_model.pkl", "tfidf_vectorizer.pkl", "shap_background.pkl")
    if any((output_dir / name).exists() for name in artifact_names) and not overwrite:
        raise FileExistsError("Output already contains model artifacts. Choose --output-dir for an experiment or pass --overwrite intentionally.")
    frame, audit = prepare_dataset(data_path)
    train_frame, test_frame = train_test_split(frame, test_size=0.2, random_state=SEED, stratify=frame["label"])
    assert not set(train_frame["normalized_text"]) & set(test_frame["normalized_text"])
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=30000, min_df=2, sublinear_tf=True)
    train_vectors = vectorizer.fit_transform(train_frame["text_"])
    test_vectors = vectorizer.transform(test_frame["text_"])
    model = LogisticRegression(max_iter=1000, random_state=SEED)
    model.fit(train_vectors, train_frame["label"])
    output_dir.mkdir(parents=True, exist_ok=True)
    for value, name in zip((model, vectorizer, train_vectors[:200]), artifact_names):
        joblib.dump(value, output_dir / name)
    report = compute_metrics(test_frame["label"].to_numpy(), model.predict(test_vectors), model.predict_proba(test_vectors)[:, list(model.classes_).index(1)])
    report.update({
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "Stratified 80/20 holdout after normalized-text deduplication and conflicting-label removal; vectorizer fitted only to training rows.",
        "provenance_status": "Generated by the reproducible training pipeline in this repository.",
        "seed": SEED,
        "train_size": len(train_frame),
        "dataset_rows": len(frame),
        "dataset_sha256": sha256(data_path),
        "model_sha256": sha256(output_dir / artifact_names[0]),
        "vectorizer_sha256": sha256(output_dir / artifact_names[1]),
        "sklearn_version": sklearn.__version__,
        "audit": audit,
        "train_test_text_overlap": 0,
        "limitations": ["A single random holdout is not external validation.", "Labels mean original vs computer-generated text, not confirmed fraud.", "No independent probability calibration or customer/product group holdout.", "Dataset external provenance and license have not been independently verified."],
    })
    (output_dir / "evaluation_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    split = {"train": [hashlib.sha256(value.encode()).hexdigest() for value in train_frame["normalized_text"]], "test": [hashlib.sha256(value.encode()).hexdigest() for value in test_frame["normalized_text"]]}
    (output_dir / "split_manifest.json").write_text(json.dumps(split, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=BASE_DIR / "dataset" / "fake_reviews.csv")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "saved_model")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = train(args.data, args.output_dir, args.overwrite)
    print(json.dumps({key: report[key] for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "train_size", "test_size", "audit")}, indent=2))
    print(f"Artifacts and evaluation report: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
