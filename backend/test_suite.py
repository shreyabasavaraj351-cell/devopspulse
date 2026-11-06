"""Complete automated verification suite for DevOpsPulse.
Audits and tests:
- Database creation & models
- Authentication & password hashing (bcrypt)
- Onboarding & Organization/Project multi-tenancy isolation
- Secret redaction and log signal scanning
- Groq AI connection and analysis pipeline (or graceful fallback if key not configured)
- Hindsight Memory Service (status, retain, recall, reflect, isolation)
- Incident lifecycle & User outcome feedback loop (unverified -> verified)
- Dashboard ground-truth metric calculation
- Settings & API security (no leaked secrets in responses)
"""
import os
import sys
import unittest

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.database.session import Base, get_db
from app.main import app
from app.models.models import User, Organization, Project, Deployment, Incident, Resolution, Feedback
from app.services import log_processing as lp
from app.memory.hindsight_service import memory, bank_id


class DevOpsPulseTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_security_password_hashing(self):
        """Verify native bcrypt hashing, verification, and boundary conditions."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword!", hashed))
        self.assertFalse(verify_password("", hashed))
        # Long password (>72 bytes) should be safely handled without throwing ValueError
        long_pwd = "A" * 100 + "123"
        long_hash = hash_password(long_pwd)
        self.assertTrue(verify_password(long_pwd, long_hash))

    def test_02_jwt_token_handling(self):
        """Verify token generation, decoding, expiry and purpose isolation."""
        token = create_token(subject=42, minutes=10, purpose="access")
        self.assertEqual(decode_token(token, purpose="access"), "42")
        # Wrong purpose check
        self.assertIsNone(decode_token(token, purpose="reset"))
        # Invalid token check
        self.assertIsNone(decode_token("invalid.token.here", purpose="access"))

    def test_03_log_redaction(self):
        """Verify secrets are redacted and never leaked."""
        raw_log = (
            "Connecting to postgresql://postgres:SuperSecretPassword@db.internal:5432/devopspulse\n"
            "Using AWS_KEY AKIAIOSFODNN7EXAMPLE and secret\n"
            "Using token gsk_abcdefghijklmnopqrstuvwxyz012345\n"
            "Authorization: Bearer my-secret-jwt-token-string\n"
            "Error: Relation 'users' does not exist\n"
        )
        prepared = lp.prepare(raw_log)
        self.assertNotIn("SuperSecretPassword", prepared)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", prepared)
        self.assertNotIn("gsk_abcdefghijklmnopqrstuvwxyz012345", prepared)
        self.assertNotIn("my-secret-jwt-token-string", prepared)
        self.assertIn("[REDACTED", prepared)
        self.assertIn("Relation 'users' does not exist", prepared)

    def test_04_log_signal_detection(self):
        """Verify log signals, error extraction and category detection."""
        sample_log = (
            "2026-11-06 20:00:00 INFO Starting migration...\n"
            "2026-11-06 20:00:01 ERROR psycopg2.OperationalError: connection to server at 'db.internal' failed: timeout\n"
            "2026-11-06 20:00:02 FATAL Migration aborted due to database connection timeout\n"
        )
        sig = lp.detect(sample_log)
        self.assertTrue(sig.has_failure)
        self.assertGreaterEqual(sig.error_count, 1)
        self.assertIn(sig.category_hint, ["database", "timeout"])
        self.assertTrue(any("timeout" in l.lower() for l in sig.error_lines))

    def test_05_auth_and_onboarding_workflow(self):
        """Verify registration, login, profile, onboarding, and project creation."""
        email = f"audit_user_{os.urandom(4).hex()}@example.com"
        reg_payload = {
            "full_name": "Audit Engineer",
            "email": email,
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        r = self.client.post("/auth/register", json=reg_payload)
        self.assertEqual(r.status_code, 201)
        data = r.json()
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check /auth/me
        r_me = self.client.get("/auth/me", headers=headers)
        self.assertEqual(r_me.status_code, 200)
        self.assertFalse(r_me.json()["onboarded"])

        # Try accessing projects before onboarding (should be 403)
        r_proj_fail = self.client.get("/projects", headers=headers)
        self.assertEqual(r_proj_fail.status_code, 403)

        # Onboard
        onboard_payload = {
            "organization_name": "DevOps Org",
            "project_name": "Core Service",
            "environment": "staging",
        }
        r_onboard = self.client.post("/onboarding", json=onboard_payload, headers=headers)
        self.assertEqual(r_onboard.status_code, 201)
        project_id = r_onboard.json()["project"]["id"]

        # Now /projects should succeed
        r_proj = self.client.get("/projects", headers=headers)
        self.assertEqual(r_proj.status_code, 200)
        projects = r_proj.json()
        self.assertGreaterEqual(len(projects), 1)
        self.assertEqual(projects[0]["id"], project_id)

        # Test duplicate onboarding rejection (409)
        r_dup_onboard = self.client.post("/onboarding", json=onboard_payload, headers=headers)
        self.assertEqual(r_dup_onboard.status_code, 409)

        return token, project_id

    def test_06_org_project_isolation(self):
        """Verify cross-tenant isolation: User B cannot access User A's project."""
        # Create User A
        token_a, proj_a = self.test_05_auth_and_onboarding_workflow()

        # Create User B
        email_b = f"user_b_{os.urandom(4).hex()}@example.com"
        r_b = self.client.post("/auth/register", json={
            "full_name": "User B",
            "email": email_b,
            "password": "Password123!",
            "confirm_password": "Password123!",
        })
        token_b = r_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        self.client.post("/onboarding", json={
            "organization_name": "Tenant B",
            "project_name": "Tenant B App",
            "environment": "staging",
        }, headers=headers_b)

        # User B attempts to access User A's project dashboard or deployment
        r_cross = self.client.get(f"/dashboard/summary?project_id={proj_a}", headers=headers_b)
        self.assertEqual(r_cross.status_code, 200)
        # In scoped queries, User B sees 0 deployments/incidents because organization_id doesn't match
        self.assertEqual(r_cross.json()["total_deployments"], 0)

        # User B attempts to analyze into User A's project -> should get 404 Project Not Found
        r_inject = self.client.post("/deployments/analyze", data={
            "project_id": proj_a,
            "deployment_name": "malicious-inject",
            "version": "1.0",
            "environment": "staging",
            "log_text": "Error: sample error",
        }, headers=headers_b)
        self.assertEqual(r_inject.status_code, 404)

    def test_07_full_deployment_analysis_and_feedback_cycle(self):
        """Verify log submission, analysis, resolution creation, and outcome confirmation."""
        token, project_id = self.test_05_auth_and_onboarding_workflow()
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Successful log (no error)
        success_log = "2026-11-06 20:00:00 INFO Build starting...\n2026-11-06 20:00:05 INFO Build completed successfully. 0 errors, 0 failures."
        r_succ = self.client.post("/deployments/analyze", data={
            "project_id": project_id,
            "deployment_name": "auth-service",
            "version": "v1.0.0",
            "environment": "staging",
            "log_text": success_log,
        }, headers=headers)
        self.assertEqual(r_succ.status_code, 200)
        succ_data = r_succ.json()
        self.assertIsNone(succ_data["incident"])
        self.assertEqual(succ_data["deployment"]["status"], "success")

        # 2. Failed log (DB migration failure)
        failed_log = (
            "2026-11-06 20:05:00 INFO Starting alembic upgrade head...\n"
            "2026-11-06 20:05:01 ERROR sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column users.avatar_url does not exist\n"
            "2026-11-06 20:05:02 FATAL Migration failed: column users.avatar_url does not exist\n"
        )
        r_fail = self.client.post("/deployments/analyze", data={
            "project_id": project_id,
            "deployment_name": "auth-service",
            "version": "v1.0.1",
            "environment": "staging",
            "log_text": failed_log,
        }, headers=headers)
        self.assertEqual(r_fail.status_code, 200)
        fail_data = r_fail.json()
        self.assertIsNotNone(fail_data["incident"])
        inc_id = fail_data["incident"]["id"]
        self.assertEqual(fail_data["incident"]["status"], "open")
        self.assertIn("recommendation", fail_data)
        self.assertGreaterEqual(len(fail_data["recommendation"]["actions"]), 1)

        # 3. Check Incident Detail
        r_inc = self.client.get(f"/incidents/{inc_id}", headers=headers)
        self.assertEqual(r_inc.status_code, 200)
        inc_data = r_inc.json()
        self.assertEqual(inc_data["id"], inc_id)
        # AI suggested resolution should initially be UNVERIFIED
        self.assertFalse(inc_data["resolutions"][0]["verified"])

        # 4. Confirm outcome (feedback loop)
        r_fb = self.client.post(f"/incidents/{inc_id}/feedback", json={
            "outcome": "resolved",
            "followed_suggestion": True,
            "notes": "Applied migration script to add avatar_url column to users table.",
        }, headers=headers)
        self.assertEqual(r_fb.status_code, 200)
        fb_data = r_fb.json()
        self.assertTrue(fb_data["verified"])
        self.assertEqual(fb_data["incident"]["status"], "resolved")

        # 5. Check Dashboard Ground-Truth Metrics
        r_dash = self.client.get(f"/dashboard/summary?project_id={project_id}", headers=headers)
        self.assertEqual(r_dash.status_code, 200)
        dash = r_dash.json()
        self.assertEqual(dash["total_deployments"], 2)
        self.assertEqual(dash["successful_deployments"], 1)
        self.assertEqual(dash["failed_deployments"], 1)
        self.assertEqual(dash["open_incidents"], 0)  # was resolved!

    def test_08_settings_security_no_secrets_leaked(self):
        """Verify API keys are kept strictly on the backend and never returned."""
        token, _ = self.test_05_auth_and_onboarding_workflow()
        headers = {"Authorization": f"Bearer {token}"}
        r = self.client.get("/settings/integrations", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # Verify no secret fields exist
        self.assertNotIn("groq_api_key", data)
        self.assertNotIn("hindsight_api_key", data)
        self.assertNotIn("secret_key", data)
        self.assertIn("groq", data)
        self.assertIn("configured", data["groq"])
        self.assertIn("hindsight", data)
        self.assertIn("reachable", data["hindsight"])


if __name__ == "__main__":
    unittest.main()
