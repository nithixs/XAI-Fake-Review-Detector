"""Real text classification and SHAP, with explicitly separate contextual rules.

The classifier learns OR (original) versus CG (computer-generated) writing patterns.
Neither that label nor the contextual score establishes whether a customer is honest.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any

MODEL_DIR = Path(__file__).resolve().parents[1] / "ai_model" / "saved_model"
MAX_REVIEW_LENGTH = 5000

METHODS = {
    "classification": "Trained TF-IDF (unigrams + bigrams) and logistic regression",
    "explanation": "SHAP LinearExplainer; interventional feature contributions in log-odds",
    "sentiment": "English lexicon rules with local negation; not a trained sentiment model",
    "aspects": "Product-aspect keywords and clause-level sentiment rules",
    "authenticity": "Heuristic context score; raw model probability plus disclosed adjustments",
}
LIMITATIONS = [
    "The training labels distinguish original and computer-generated reviews; they are not verified fraud labels.",
    "Predictions are screening signals, not proof of deception. Human review is required.",
    "The text model and sentiment rules target English; sarcasm, other languages and domain shifts can fail.",
    "Model probabilities are not independently calibrated to real-world fraud rates.",
    "The authenticity score and sentiment/aspect labels use disclosed rules, not additional trained models.",
]

POSITIVE = set("good great excellent amazing awesome fantastic wonderful superb perfect love loved like liked enjoy enjoyed recommend recommended happy satisfied useful helpful comfortable comfort clear crisp durable reliable affordable value smooth easy fast quick beautiful nice impressive quality powerful lightweight soft sturdy pleasant bright accurate responsive efficient convenient solid premium best works working worth delicious tasty clean quiet spacious sharp vibrant fit fits supportive breathable refreshing rich fresh balanced immersive versatile".split())
NEGATIVE = set("bad poor terrible awful horrible worst hate hated dislike disappointed disappointing broken defective damaged useless uncomfortable unclear unreliable expensive overpriced slow difficult noisy weak cheap frustrating issue issues problem problems faulty waste dull heavy lag laggy disconnect disconnects uncomfortable uncomfortable drain drains draining fails failed failure stopped missing misleading late delay delayed bitter stale flimsy rough blurry inaccurate tight loose leaks leaking scratch scratches scratchy".split())
NEUTRAL = set("average okay ok ordinary moderate decent acceptable normal fair".split())
NEGATORS = {"not", "no", "never", "neither", "hardly", "barely", "without"}
ASPECT_KEYWORDS = {
    "Sound quality": {"sound", "audio", "bass", "treble", "volume", "speaker", "speakers", "microphone", "mic", "noise"},
    "Battery": {"battery", "batteries", "charging", "charge", "charger", "backup"},
    "Connectivity": {"bluetooth", "connection", "connectivity", "pairing", "wifi", "wireless", "disconnect", "disconnects"},
    "Comfort": {"comfort", "comfortable", "uncomfortable", "fit", "fits", "soft", "wear", "cushion", "cushions"},
    "Price": {"price", "cost", "value", "money", "affordable", "expensive", "overpriced", "worth"},
    "Build quality": {"build", "quality", "durability", "durable", "material", "materials", "sturdy", "plastic", "flimsy"},
    "Display": {"display", "screen", "brightness", "resolution", "colors", "colour", "monitor"},
    "Performance": {"performance", "speed", "processor", "lag", "laggy", "responsive", "smooth", "tracking", "accuracy", "accurate"},
    "Delivery": {"delivery", "shipping", "packaging", "package", "arrived", "courier"},
    "Design": {"design", "style", "look", "looks", "appearance", "color", "colour", "weight"},
    "Camera": {"camera", "photo", "photos", "picture", "pictures", "video"},
    "Taste": {"taste", "flavor", "flavour", "coffee", "tasty", "delicious", "bitter", "fresh", "stale"},
}


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("\u2019", "'")
    text = re.sub(r"\b(can|could|does|did|is|was|would|should|has|have|are|were|do)n['’]t\b", r"\1 not", text)
    text = re.sub(r"\bwon't\b", "will not", text)
    text = re.sub(r"\bcan't\b", "can not", text)
    return re.findall(r"[a-z]+", text)


def _opinion_value(tokens: list[str], index: int) -> float:
    token = tokens[index]
    # 'quality' alone is an aspect, rather than an opinion.
    if token == "quality":
        return 0.0
    value = 1.0 if token in POSITIVE else -1.0 if token in NEGATIVE else 0.0
    prefix = tokens[max(0, index - 3):index]
    negations = sum(word in NEGATORS for word in prefix)
    if "not" in prefix and "only" in prefix:
        negations -= 1
    return -value if negations % 2 else value


def _sentiment_score(text: str) -> float:
    tokens = _tokens(text)
    return sum(_opinion_value(tokens, index) for index in range(len(tokens)))


def _label(score: float) -> str:
    return "Positive" if score > 0 else "Negative" if score < 0 else "Neutral"


def analyze_sentiment_and_aspects(review: str) -> tuple[str, list[dict[str, str]]]:
    """Small, deterministic English baseline; mixed clauses keep separate aspects."""
    clauses = [part.strip() for part in re.split(r"[.!?;,\n]+|\b(?:but|however|although|yet|whereas|while|and)\b", review, flags=re.I) if part.strip()]
    aspect_scores: dict[str, list[float]] = {}
    for clause in clauses:
        words = _tokens(clause)
        matches = {aspect: [i for i, word in enumerate(words) if word in keywords] for aspect, keywords in ASPECT_KEYWORDS.items()}
        matches = {aspect: positions for aspect, positions in matches.items() if positions}
        # 'sound quality' is the sound aspect, not an independent build-quality claim.
        if "Sound quality" in matches and set(words) & {"sound", "audio"} and not set(words) & {"build", "material", "durable", "plastic"}:
            matches.pop("Build quality", None)
        for aspect, positions in matches.items():
            if len(matches) == 1:
                score = _sentiment_score(clause)
            else:
                # Attribute opinion words to the nearest mentioned aspect.
                score = 0.0
                for i, word in enumerate(words):
                    if word not in POSITIVE | NEGATIVE or word == "quality":
                        continue
                    nearest = min(matches, key=lambda key: min(abs(i - p) for p in matches[key]))
                    if nearest == aspect:
                        score += _opinion_value(words, i)
            aspect_scores.setdefault(aspect, []).append(score)
    aspects = [{"aspect": aspect, "sentiment": _label(sum(scores))} for aspect, scores in aspect_scores.items()]
    return _label(sum(_sentiment_score(clause) for clause in clauses)), aspects


@lru_cache(maxsize=1)
def _load_model():
    import joblib
    import numpy as np
    import shap

    expected = ("fake_review_model.pkl", "tfidf_vectorizer.pkl", "shap_background.pkl")
    missing = [name for name in expected if not (MODEL_DIR / name).is_file()]
    if missing:
        raise RuntimeError("Missing model artifacts: " + ", ".join(missing) + ". Run python -m ai_model.train_model.")
    # Only load trusted local artifacts; pickle is never accepted through the API.
    model, vectorizer, background = (joblib.load(MODEL_DIR / name) for name in expected)
    classes = list(model.classes_)
    if len(classes) != 2 or set(classes) != {0, 1}:
        raise RuntimeError("Expected binary model labels 0=original and 1=computer-generated.")
    if len(vectorizer.get_feature_names_out()) != model.coef_.shape[1] or background.shape[1] != model.coef_.shape[1]:
        raise RuntimeError("The model, vectorizer and SHAP background have incompatible dimensions.")
    # Keep all 200 saved background examples, instead of the masker's default subsample.
    masker = shap.maskers.Independent(background, max_samples=background.shape[0])
    explainer = shap.LinearExplainer(model, masker)
    fingerprint = hashlib.sha256((MODEL_DIR / expected[0]).read_bytes()).hexdigest()
    return model, vectorizer, explainer, np, fingerprint


def _context_adjustments(context: dict[str, Any] | None) -> tuple[float, list[dict[str, Any]]]:
    if context is None:
        return 0.0, [{"label": "Text-only analysis", "detail": "No purchase or customer history was supplied; no contextual adjustment.", "impact": 0}]
    signals = []
    if context.get("verified_purchase") is True:
        signals.append({"label": "Verified purchase", "detail": "A matching customer order exists. This supports purchase context, not review truthfulness.", "impact": 8})
    else:
        signals.append({"label": "Purchase not verified", "detail": "No matching order was found; this alone is not evidence of a fake review.", "impact": 0})
    duplicates = max(0, int(context.get("duplicate_count") or 0))
    if duplicates:
        signals.append({"label": "Repeated review text", "detail": f"The same normalized text appears in {duplicates} other review(s).", "impact": -min(25, 10 + 5 * duplicates)})
    recent = max(0, int(context.get("recent_review_count") or 0))
    if recent >= 5:
        signals.append({"label": "Review activity burst", "detail": f"This customer submitted {recent} other reviews in the past 24 hours.", "impact": -min(15, recent)})
    count = max(0, int(context.get("review_count") or 0))
    signals.append({"label": "Customer history", "detail": f"{count} previous review(s). Account activity alone does not establish authenticity.", "impact": 0})
    product = context.get("product") or {}
    if product.get("name"):
        signals.append({"label": "Product context", "detail": f"Review linked to {product['name']} ({product.get('category', 'Uncategorized')}). Product identity is recorded; it does not change the trained text model.", "impact": 0})
    return float(sum(signal["impact"] for signal in signals)), signals


def analyze_review(review: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(review, str) or not review.strip():
        raise ValueError("Review cannot be empty.")
    review = review.strip()
    if len(review) > MAX_REVIEW_LENGTH:
        raise ValueError(f"Review must contain at most {MAX_REVIEW_LENGTH} characters.")
    model, vectorizer, explainer, np, fingerprint = _load_model()
    vector = vectorizer.transform([review])
    classes = list(model.classes_)
    probabilities = model.predict_proba(vector)[0]
    fake = float(probabilities[classes.index(1)] * 100)
    genuine = float(probabilities[classes.index(0)] * 100)
    predicted_class = int(model.predict(vector)[0])
    orientation = 1 if classes[1] == 1 else -1
    values = np.asarray(explainer.shap_values(vector))[0] * orientation
    base = float(np.asarray(explainer.expected_value).reshape(-1)[0]) * orientation
    log_odds = float(model.decision_function(vector)[0]) * orientation
    names = vectorizer.get_feature_names_out()
    explanation = sorted([
        {"feature": str(names[index]), "shap_value": float(values[index]), "influence": "Fake" if values[index] > 0 else "Genuine"}
        for index in vector.indices if abs(float(values[index])) > 1e-12
    ], key=lambda item: abs(item["shap_value"]), reverse=True)[:12]
    full_sum = float(values.sum())
    displayed_sum = sum(item["shap_value"] for item in explanation)
    sentiment, aspects = analyze_sentiment_and_aspects(review)
    adjustment, signals = _context_adjustments(context)
    limitations = list(LIMITATIONS)
    feature_count = int(vector.nnz)
    if feature_count == 0:
        limitations.insert(0, "No known English vocabulary features were found. The returned probability is only the model's intercept prior and is not reliable evidence about this review.")
    elif len(_tokens(review)) < 5:
        limitations.insert(0, "This review is very short; the text model has limited evidence.")
    xai = {
        "base_value": base,
        "full_contribution_sum": full_sum,
        "displayed_contribution_sum": displayed_sum,
        "other_contributions": full_sum - displayed_sum,
        "log_odds": log_odds,
        "reconstructed_log_odds": base + full_sum,
        "additivity_error": abs(base + full_sum - log_odds),
        "units": "log-odds",
        "note": "Shown words are present in the review. Other contributions include omitted and absent vocabulary features; only the full sum reconstructs the prediction.",
    }
    return {
        "review": review,
        "prediction": "Fake / Suspicious" if predicted_class == 1 else "Genuine",
        "confidence": round(fake if predicted_class == 1 else genuine, 2),
        "fake_probability": round(fake, 2),
        "genuine_probability": round(genuine, 2),
        "explanation": explanation,
        "sentiment": sentiment,
        "aspects": aspects,
        "authenticity_score": round(max(0, min(100, genuine + adjustment)), 2),
        "context_adjustment": adjustment,
        "context_signals": signals,
        "analysis_method": dict(METHODS),
        "limitations": limitations,
        "feature_coverage": {"matched_features": feature_count, "sufficient_evidence": feature_count > 0},
        "xai": xai,
        "base_value": base,
        "full_contribution_sum": full_sum,
        "log_odds": log_odds,
        "model_version": "tfidf-lr-" + fingerprint[:12],
    }


def get_model_info() -> dict[str, Any]:
    model, vectorizer, explainer, _, fingerprint = _load_model()
    metrics_path = MODEL_DIR / "evaluation_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else None
    # Never attribute metrics to a different set of artifact bytes after retraining.
    vectorizer_fingerprint = hashlib.sha256((MODEL_DIR / "tfidf_vectorizer.pkl").read_bytes()).hexdigest()
    if metrics and (metrics.get("model_sha256") != fingerprint or metrics.get("vectorizer_sha256") != vectorizer_fingerprint):
        metrics = None
    return {
        "status": "ready",
        "name": "TF-IDF + Logistic Regression",
        "version": "tfidf-lr-" + fingerprint[:12],
        "model_sha256": fingerprint,
        "features": int(model.coef_.shape[1]),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "ngram_range": list(vectorizer.ngram_range),
        "classes": {"0": "Original review (OR)", "1": "Computer-generated review (CG)"},
        "decision_threshold": 0.5,
        "explainability": "SHAP LinearExplainer",
        "shap_background_size": int(explainer.masker.data.shape[0]),
        "methods": dict(METHODS),
        "dataset": {"file": "ai_model/dataset/fake_reviews.csv", "label_meaning": "OR=original; CG=computer-generated", "provenance": "Existing project dataset; external source and license have not been independently verified."},
        "metrics": metrics,
        "metrics_status": "available" if metrics else "No matching evaluation report. Run python -m ai_model.evaluate_model.",
        "limitations": list(LIMITATIONS),
    }
