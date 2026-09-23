"""Integration tests use a temporary SQLite database and the real saved ML model."""
from pathlib import Path
import os
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="reviewguard-tests-")
        cls.previous = {key: os.environ.get(key) for key in ("DB_ENGINE", "SQLITE_PATH", "SEED_DEMO")}
        os.environ.update(DB_ENGINE="sqlite", SQLITE_PATH=str(Path(cls.directory.name) / "test.db"), SEED_DEMO="true")
        from backend.main import app
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.products = cls.client.get("/api/products").json()
        response = cls.client.post("/api/auth/login", json={"email": "admin@reviewguard.demo", "password": "Admin@12345"})
        if response.status_code != 200:
            raise AssertionError(response.text)
        cls.admin_headers = {"Authorization": "Bearer " + response.json()["token"]}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.directory.cleanup()
        for key, value in cls.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def register(self):
        email = f"student-{uuid.uuid4().hex}@example.com"
        response = self.client.post("/api/auth/register", json={"name": "Test Student", "email": email, "password": "Student@123"})
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        return {"Authorization": "Bearer " + payload["token"]}, payload["user"], email

    def review(self, headers, product_id, text="The sound is clear and comfortable, but the battery life is poor."):
        return self.client.post(f"/api/products/{product_id}/reviews", headers=headers, json={"rating": 4, "review": text})

    def test_catalogue_and_filtering(self):
        self.assertGreaterEqual(len(self.products), 6)
        product = self.products[0]
        self.assertEqual(self.client.get(f"/api/products/{product['id']}").status_code, 200)
        matches = self.client.get("/api/products", params={"search": product["name"]}).json()
        self.assertEqual(matches[0]["id"], product["id"])
        self.assertEqual(self.client.get("/api/products", params={"search": "no-such-product-xyz"}).json(), [])
        self.assertEqual(self.client.get("/api/products/999999").status_code, 404)

    def test_registration_login_logout_and_no_role_injection(self):
        headers, user, email = self.register()
        self.assertEqual(user["role"], "customer")
        self.assertNotIn("password_hash", user)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["id"], user["id"])
        self.assertEqual(self.client.post("/api/auth/register", json={"name": "Duplicate", "email": email.upper(), "password": "Student@123"}).status_code, 409)
        self.assertEqual(self.client.post("/api/auth/register", json={"name": "Attacker", "email": "attack@example.com", "password": "Student@123", "role": "admin"}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": email, "password": "incorrect-password"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_customer_cannot_use_admin_routes(self):
        headers, _, _ = self.register()
        self.assertEqual(self.client.get("/api/orders").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/stats").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/stats", headers=headers).status_code, 403)
        self.assertEqual(self.client.patch("/api/admin/reviews/1", headers=headers, json={"status": "removed"}).status_code, 403)

    def test_purchase_verification_and_order_isolation(self):
        headers, _, _ = self.register()
        other_headers, _, _ = self.register()
        product = self.products[0]
        self.assertEqual(self.client.post("/api/orders", headers=headers, json={"product_id": product["id"], "quantity": 2, "unit_price": 0}).status_code, 422)
        order = self.client.post("/api/orders", headers=headers, json={"product_id": product["id"], "quantity": 2})
        self.assertEqual(order.status_code, 201, order.text)
        self.assertEqual(order.json()["total"], product["price"] * 2)
        self.assertTrue(order.json()["is_demo"])
        self.assertEqual(len(self.client.get("/api/orders", headers=headers).json()), 1)
        self.assertEqual(self.client.get("/api/orders", headers=other_headers).json(), [])
        response = self.review(headers, product["id"])
        self.assertEqual(response.status_code, 201, response.text)
        self.assertTrue(response.json()["verified_purchase"])
        self.assertEqual(self.review(headers, product["id"]).status_code, 409)

    def test_moderation_does_not_fake_a_purchase_and_updates_analytics(self):
        headers, _, _ = self.register()
        product_id = self.products[1]["id"]
        created = self.review(headers, product_id).json()
        self.assertFalse(created["verified_purchase"])
        before = self.client.get(f"/api/products/{product_id}/analytics").json()["total_reviews"]
        url = f"/api/admin/reviews/{created['id']}"
        verified = self.client.patch(url, headers=self.admin_headers, json={"status": "verified"})
        self.assertEqual(verified.status_code, 200)
        self.assertFalse(verified.json()["verified_purchase"])
        self.assertEqual(verified.json()["moderation_status"], "verified")
        self.assertEqual(self.client.patch(url, headers=self.admin_headers, json={"status": "removed"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/products/{product_id}/analytics").json()["total_reviews"], before - 1)
        self.assertNotIn(created["id"], [x["id"] for x in self.client.get(f"/api/products/{product_id}/reviews").json()])
        own = self.client.get("/api/me/reviews", headers=headers).json()
        self.assertEqual(own[0]["moderation_status"], "removed")
        self.assertEqual(self.client.patch(url, headers=self.admin_headers, json={"status": "active"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/products/{product_id}/analytics").json()["total_reviews"], before)

    def test_validation_and_nonexistent_resources(self):
        headers, _, _ = self.register()
        for review in ("", "         ", "short", "x" * 5001):
            self.assertEqual(self.client.post("/api/predict", json={"review": review}).status_code, 422)
        for rating in (0, 6, True, 3.5):
            self.assertEqual(self.client.post("/api/products/1/reviews", headers=headers, json={"rating": rating, "review": "A detailed customer review."}).status_code, 422)
        self.assertEqual(self.client.post("/api/orders", headers=headers, json={"product_id": 999999}).status_code, 404)
        self.assertEqual(self.client.post("/api/orders", headers=headers, json={"product_id": 1, "quantity": 0}).status_code, 422)
        self.assertEqual(self.client.patch("/api/admin/reviews/999999", headers=self.admin_headers, json={"status": "removed"}).status_code, 404)

    def test_real_prediction_shap_and_legacy_history(self):
        response = self.client.post("/api/predict", json={"review": "I used these headphones for two weeks. Sound quality is good but the battery is poor."})
        self.assertEqual(response.status_code, 200, response.text)
        analysis = response.json()
        self.assertAlmostEqual(analysis["fake_probability"] + analysis["genuine_probability"], 100, places=1)
        self.assertGreater(len(analysis["explanation"]), 0)
        self.assertIn(analysis["sentiment"], ("Positive", "Neutral", "Negative"))
        self.assertTrue(analysis["aspects"])
        self.assertLess(abs(analysis["xai"]["additivity_error"]), 0.00001)
        self.assertEqual(self.client.get("/history").json()[0]["review"], analysis["review"])
        self.assertGreater(self.client.get("/stats").json()["total_reviews"], 0)

    def test_analytics_counts_reconcile(self):
        product_id = self.products[0]["id"]
        analytics = self.client.get(f"/api/products/{product_id}/analytics").json()
        self.assertEqual(sum(analytics["rating_distribution"].values()), analytics["total_reviews"])
        self.assertEqual(sum(item["count"] for item in analytics["sentiment"].values()), analytics["total_reviews"])
        stats = self.client.get("/api/admin/stats", headers=self.admin_headers).json()
        self.assertEqual(stats["genuine_reviews"] + stats["suspicious_reviews"], stats["total_reviews"])


if __name__ == "__main__":
    unittest.main()
