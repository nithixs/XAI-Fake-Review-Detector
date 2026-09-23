"""Provision an administrator from private deployment variables, never HTTP."""
import os

from backend import database as db
from backend.security import hash_password


def provision_admin():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email and not password:
        return
    if "@" not in email or len(password) < 16:
        raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD (at least 16 characters) are required")
    existing = db.get_user_by_email(email)
    if existing:
        if existing["role"] != "admin" or existing.get("is_demo"):
            raise ValueError("Administrator provisioning cannot promote an existing account")
        return
    db.create_user("ReviewGuard Admin", email, hash_password(password), "admin")
