import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import database as db
from backend.provision import provision_admin
from backend.security import verify_password
from backend.seed import seed_catalogue


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DB_ENGINE": "sqlite", "SQLITE_PATH": str(Path(self.directory.name) / "db.sqlite"),
            "ADMIN_EMAIL": "owner@example.com", "ADMIN_PASSWORD": "Private-test-password-123",
        })
        self.env.start()
        db.create_tables()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_catalogue_does_not_create_shared_accounts(self):
        seed_catalogue()
        seed_catalogue()
        self.assertEqual(len(db.list_products()), 6)
        self.assertIsNone(db.get_user_by_email("admin@reviewguard.demo"))
        self.assertIsNone(db.get_user_by_email("customer@reviewguard.demo"))

    def test_admin_creation_is_idempotent(self):
        provision_admin()
        user = db.get_user_by_email("owner@example.com")
        self.assertEqual(user["role"], "admin")
        self.assertTrue(verify_password("Private-test-password-123", user["password_hash"]))
        provision_admin()
        self.assertEqual(user["id"], db.get_user_by_email("owner@example.com")["id"])

    def test_customer_cannot_be_promoted(self):
        db.create_user("Customer", "owner@example.com", "unused", "customer")
        with self.assertRaises(ValueError):
            provision_admin()
        self.assertEqual(db.get_user_by_email("owner@example.com")["role"], "customer")

    def test_short_password_rejected(self):
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "short"}):
            with self.assertRaises(ValueError):
                provision_admin()
