import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.services.credential_cipher import CredentialCipher
from src.services.job_store import JobStore


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.database_path = root / "test.db"
        self.store = JobStore(
            str(self.database_path), CredentialCipher(key_path=root / ".key")
        )
        self.client_context = TestClient(
            create_app(store=self.store, start_dispatcher=False)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def upload_batch(self, platform="twitter"):
        return self.client.post(
            f"/api/v1/platforms/{platform}/batches",
            data={"name": "Launch team"},
            files={"file": ("accounts.csv", b"username,password\nalice,top-secret\n", "text/csv")},
        )

    def test_upload_is_platform_scoped_and_password_is_encrypted(self):
        response = self.upload_batch()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["platform"], "twitter")
        self.assertEqual(response.json()["account_count"], 1)

        batches = self.client.get("/api/v1/platforms/twitter/batches").json()
        self.assertEqual(len(batches), 1)
        self.assertNotIn("password", batches[0])

        with sqlite3.connect(self.database_path) as connection:
            ciphertext = connection.execute(
                "SELECT password_ciphertext FROM accounts"
            ).fetchone()[0]
        self.assertNotIn("top-secret", ciphertext)
        self.assertEqual(self.store.load_accounts(response.json()["id"])[0].password, "top-secret")

    def test_job_submission_returns_queued_without_running_browser(self):
        batch_id = self.upload_batch().json()["id"]
        response = self.client.post(
            "/api/v1/jobs",
            json={
                "batch_id": batch_id,
                "action": "like",
                "target_url": "https://x.com/example/status/123",
            },
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["total"], 1)

    def test_rejects_target_for_different_platform(self):
        batch_id = self.upload_batch().json()["id"]
        response = self.client.post(
            "/api/v1/jobs",
            json={
                "batch_id": batch_id,
                "action": "like",
                "target_url": "https://instagram.com/p/123/",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_serves_ui(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SOCIAL OPERATIONS CONSOLE", response.text)


if __name__ == "__main__":
    unittest.main()
