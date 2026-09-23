"""Behavioral tests against the actual shipped classifier and SHAP artifacts."""

import math
from pathlib import Path
import tempfile
import unittest

from backend.intelligence import analyze_review, analyze_sentiment_and_aspects, get_model_info


class IntelligenceTests(unittest.TestCase):
    REVIEW = "The sound is clear and the headphones are comfortable, but the battery is poor."

    def test_real_model_probability_and_shap_additivity(self):
        result = analyze_review(self.REVIEW)
        self.assertAlmostEqual(result["fake_probability"] + result["genuine_probability"], 100, places=2)
        self.assertLess(result["xai"]["additivity_error"], 1e-8)
        reconstructed_probability = 100 / (1 + math.exp(-result["xai"]["reconstructed_log_odds"]))
        self.assertAlmostEqual(reconstructed_probability, result["fake_probability"], places=2)
        self.assertGreater(len(result["explanation"]), 0)
        self.assertAlmostEqual(sum(row["shap_value"] for row in result["explanation"]) + result["xai"]["other_contributions"], result["full_contribution_sum"])

    def test_context_cannot_rewrite_trained_prediction(self):
        plain = analyze_review(self.REVIEW)
        verified = analyze_review(self.REVIEW, {"verified_purchase": True, "review_count": 2})
        duplicate = analyze_review(self.REVIEW, {"verified_purchase": True, "duplicate_count": 2, "recent_review_count": 6})
        for result in (verified, duplicate):
            self.assertEqual(result["fake_probability"], plain["fake_probability"])
            self.assertEqual(result["prediction"], plain["prediction"])
            self.assertEqual(result["explanation"], plain["explanation"])
        self.assertGreaterEqual(verified["authenticity_score"], plain["authenticity_score"])
        self.assertLess(duplicate["authenticity_score"], verified["authenticity_score"])
        self.assertTrue(any(signal["impact"] < 0 for signal in duplicate["context_signals"]))

    def test_missing_purchase_does_not_imply_fraud(self):
        plain = analyze_review(self.REVIEW)
        unverified = analyze_review(self.REVIEW, {"verified_purchase": False})
        self.assertEqual(plain["authenticity_score"], unverified["authenticity_score"])

    def test_empty_and_long_input_rejected(self):
        for review in ("", "   ", "a" * 5001, None):
            with self.assertRaises(ValueError):
                analyze_review(review)

    def test_unknown_vocabulary_is_disclosed(self):
        result = analyze_review("zzqxvv qqzxvv")
        self.assertEqual(result["feature_coverage"]["matched_features"], 0)
        self.assertFalse(result["feature_coverage"]["sufficient_evidence"])
        self.assertEqual(result["explanation"], [])
        self.assertIn("intercept prior", result["limitations"][0])

    def test_aspects_respect_mixed_clauses_and_negation(self):
        _, aspects = analyze_sentiment_and_aspects("Sound quality is amazing but battery is average and bluetooth is not reliable.")
        values = {row["aspect"]: row["sentiment"] for row in aspects}
        self.assertEqual(values["Sound quality"], "Positive")
        self.assertEqual(values["Battery"], "Neutral")
        self.assertEqual(values["Connectivity"], "Negative")
        self.assertEqual(analyze_sentiment_and_aspects("The battery isn't good.")[0], "Negative")
        self.assertEqual(analyze_sentiment_and_aspects("The sound is not bad.")[0], "Positive")
        _, adjacent = analyze_sentiment_and_aspects("Sound great battery bad")
        self.assertEqual({row["aspect"]: row["sentiment"] for row in adjacent}, {"Sound quality": "Positive", "Battery": "Negative"})

    def test_model_card_describes_actual_features_and_methods(self):
        info = get_model_info()
        self.assertEqual(info["status"], "ready")
        self.assertGreater(info["features"], 100)
        self.assertIn("not a trained", info["methods"]["sentiment"])
        if info["metrics"]:
            self.assertEqual(info["metrics"]["model_sha256"], info["model_sha256"])

    def test_training_removes_duplicates_and_conflicting_labels_before_split(self):
        import pandas as pd
        from ai_model.train_model import prepare_dataset
        rows = [{"text_": f"A distinct original review {i}", "label": "OR"} for i in range(6)]
        rows += [{"text_": f"A distinct generated review {i}", "label": "CG"} for i in range(6)]
        rows += [{"text_": "  A DISTINCT original review 0  ", "label": "OR"}]
        rows += [{"text_": "conflicting text", "label": label} for label in ("OR", "CG")]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            frame, audit = prepare_dataset(path)
        self.assertEqual(len(frame), 12)
        self.assertEqual(audit["duplicate_rows_removed"], 1)
        self.assertEqual(audit["conflicting_rows_removed"], 2)


if __name__ == "__main__":
    unittest.main()
