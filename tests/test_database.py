"""Persistence tests use isolated temporary databases and explicit AI fixtures."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import database as db


def fixture_analysis(review, context=None):
    return {
        "prediction": "Genuine", "confidence": 80, "fake_probability": 20,
        "genuine_probability": 80, "authenticity_score": 75,
        "sentiment": {"label": "Positive"},
        "aspects": [{"aspect": "Sound", "sentiment": "Positive"}],
        "explanation": [],
    }


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "DB_ENGINE": "sqlite", "SQLITE_PATH": str(Path(self.temp.name) / "test.db"), "SEED_DEMO": "true",
        })
        self.environment.start()
        db.create_tables()
        db.seed_demo(fixture_analysis, lambda value: "test_hash:" + value)
        self.customer = db.create_user("New Customer", "new@example.test", "test_hash")
        self.admin = db.get_user_by_email("admin@reviewguard.demo")
        self.product = db.list_products()[0]

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def review(self, product_id=None, analysis=None):
        return db.create_product_review(self.customer["id"], product_id or self.product["id"],
                                         4, "Clear sound and comfortable fit.", analysis or fixture_analysis(""))

    def test_schema_and_seed_are_idempotent_and_preserve_history(self):
        db.save_review("Original review", "Genuine", 90, 10, 90)
        before = db.get_admin_stats()
        db.create_tables()
        result = db.seed_demo(fixture_analysis, lambda value: "different_hash")
        self.assertEqual(result["reviews_created"], 0)
        self.assertEqual(len(db.list_products()), 6)
        self.assertEqual(db.get_admin_stats(), before)
        self.assertEqual(db.get_review_history()[0]["review"], "Original review")
        self.assertEqual(db.get_dashboard_stats()["total_reviews"], 1)
        self.assertTrue(db.get_user_by_email("admin@reviewguard.demo")["password_hash"].startswith("test_hash:"))

    def test_purchase_verification_is_customer_and_product_scoped(self):
        forged = {**fixture_analysis(""), "verified_purchase": True}
        review = self.review(analysis=forged)
        self.assertFalse(review["verified_purchase"])
        other = db.list_products()[1]
        db.create_order(self.customer["id"], other["id"])
        self.assertFalse(db.get_product_review(review["id"])["verified_purchase"])
        order = db.create_order(self.customer["id"], self.product["id"], 2)
        self.assertTrue(order["is_demo"])
        self.assertEqual(order["total"], self.product["price"] * 2)
        self.assertTrue(db.get_product_review(review["id"])["verified_purchase"])

    def test_order_retains_purchase_time_price(self):
        order = db.create_order(self.customer["id"], self.product["id"])
        with db._cursor() as cursor:
            db._execute(cursor, "UPDATE products SET price = ? WHERE id = ?", (9999, self.product["id"]))
        self.assertEqual(db.get_orders(self.customer["id"])[0]["unit_price"], order["unit_price"])

    def test_unique_review_constraint(self):
        self.review()
        with self.assertRaisesRegex(ValueError, "already reviewed"):
            self.review()

    def test_moderation_is_audited_and_does_not_verify_purchase(self):
        review = self.review()
        with self.assertRaises(PermissionError):
            db.moderate_review(review["id"], "verified", self.customer["id"])
        verified = db.moderate_review(review["id"], "verified", self.admin["id"])
        self.assertEqual(verified["moderation_status"], "verified")
        self.assertFalse(verified["verified_purchase"])
        with db._cursor() as cursor:
            count = db._execute(cursor, "SELECT COUNT(*) FROM review_moderation_log").fetchone()[0]
        self.assertEqual(count, 1)

    def test_soft_removal_excludes_public_analytics_and_is_reversible(self):
        review = self.review()
        count_before = db.get_product_analytics(self.product["id"])["total_reviews"]
        db.moderate_review(review["id"], "removed", self.admin["id"])
        self.assertNotIn(review["id"], [item["id"] for item in db.list_product_reviews(self.product["id"])])
        self.assertEqual(db.get_product_analytics(self.product["id"])["total_reviews"], count_before - 1)
        self.assertEqual(db.get_product(self.product["id"])["total_reviews"], count_before - 1)
        self.assertEqual(db.list_admin_reviews("removed")[0]["id"], review["id"])
        db.moderate_review(review["id"], "active", self.admin["id"])
        self.assertEqual(db.get_product_analytics(self.product["id"])["total_reviews"], count_before)

    def test_session_expiry_revocation_and_hash_privacy(self):
        now = datetime.now(timezone.utc)
        db.create_session(self.customer["id"], "expired-token-hash", now - timedelta(minutes=1))
        self.assertIsNone(db.get_session_user("expired-token-hash"))
        db.create_session(self.customer["id"], "active-token-hash", now + timedelta(hours=1))
        user = db.get_session_user("active-token-hash")
        self.assertEqual(user["id"], self.customer["id"])
        self.assertNotIn("password_hash", user)
        db.delete_session("active-token-hash")
        self.assertIsNone(db.get_session_user("active-token-hash"))

    def test_user_context_normalizes_duplicates(self):
        self.review()
        context = db.user_review_context(self.customer["id"], "  CLEAR sound   and comfortable fit.  ")
        self.assertEqual(context, {"review_count": 1, "recent_review_count": 1, "duplicate_count": 1})

    def test_email_uniqueness_and_bound_search_parameters(self):
        with self.assertRaises(ValueError):
            db.create_user("Duplicate", "NEW@example.test", "hash")
        self.assertEqual(db.list_products("' OR 1=1 --"), [])
        self.assertEqual(db.list_products(category="Audio")[0]["category"], "Audio")
        self.assertEqual(len(db.list_products()), 6)

    def test_json_serialization_and_empty_analytics(self):
        json.dumps(db.list_products())
        json.dumps(db.get_product_analytics(self.product["id"]))
        json.dumps(db.get_admin_stats())
        self.assertIsNone(db.get_product_analytics(999999))

    def test_seed_does_not_promote_or_reset_existing_account(self):
        with db._cursor() as cursor:
            db._execute(cursor, "UPDATE app_users SET role = 'customer', is_demo = 0 WHERE id = ?", (self.admin["id"],))
        db.seed_demo(fixture_analysis, lambda value: "replacement")
        existing = db.get_user_by_email("admin@reviewguard.demo")
        self.assertEqual(existing["role"], "customer")
        self.assertEqual(existing["password_hash"], self.admin["password_hash"])

    def test_seed_respects_demo_disabled(self):
        with patch.dict(os.environ, {"SEED_DEMO": "false"}):
            self.assertFalse(db.seed_demo(fixture_analysis, lambda value: "hash")["seeded"])


if __name__ == "__main__":
    unittest.main()
