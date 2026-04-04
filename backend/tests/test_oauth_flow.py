import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.secret_store import secret_store
from config.store import config_store
from connections import oauth
from gateway.routes.setup import router as setup_router


class OAuthFlowTests(unittest.TestCase):
    def setUp(self):
        self.config_data = {
            "google_oauth_client_id": "client-id",
            "google_oauth_client_secret": "client-secret",
            "google_oauth_redirect_uri": "http://localhost/oauth/callback",
            "external_connections": {},
        }
        self.secret_data = {}
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_config_delete = config_store.delete
        self._orig_secret_get = secret_store.get
        self._orig_secret_set = secret_store.set
        self._orig_secret_delete = secret_store.delete
        self._orig_secret_backend = secret_store.backend

        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = self._config_set
        config_store.delete = self._config_delete
        secret_store.get = lambda key: self.secret_data.get(key)
        secret_store.set = self._secret_set
        secret_store.delete = self._secret_delete
        secret_store.backend = lambda key: "config"
        oauth._oauth_states.clear()

        app = FastAPI()
        app.include_router(setup_router)
        self.client = TestClient(app)

    def tearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        config_store.delete = self._orig_config_delete
        secret_store.get = self._orig_secret_get
        secret_store.set = self._orig_secret_set
        secret_store.delete = self._orig_secret_delete
        secret_store.backend = self._orig_secret_backend
        oauth._oauth_states.clear()

    def _config_set(self, key, value):
        self.config_data[key] = value

    def _config_delete(self, key):
        self.config_data.pop(key, None)

    def _secret_set(self, key, value):
        self.secret_data[key] = value
        return True, None

    def _secret_delete(self, key):
        self.secret_data.pop(key, None)
        return True, None

    def _authorize(self, connection_id: str) -> dict:
        response = self.client.post(f"/setup/connections/{connection_id}/authorize")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _extract_query(self, auth_url: str) -> dict[str, list[str]]:
        return parse_qs(urlparse(auth_url).query)

    def test_google_calendar_authorize_returns_auth_url_with_scope_and_state(self):
        payload = self._authorize("google_calendar")

        auth_url = payload["auth_url"]
        self.assertIn("accounts.google.com", auth_url)
        query = self._extract_query(auth_url)
        self.assertEqual(query["scope"][0], "https://www.googleapis.com/auth/calendar")
        self.assertTrue(query["state"][0])

    def test_callback_with_valid_code_and_state_marks_connection_configured_and_stores_tokens(self):
        authorize_payload = self._authorize("google_calendar")
        state = self._extract_query(authorize_payload["auth_url"])["state"][0]

        with patch.object(
            oauth,
            "_post_form",
            return_value={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        ):
            response = self.client.post(
                "/setup/connections/google_calendar/callback",
                json={"code": "valid-code", "state": state},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["connection"]["configured"])
        self.assertTrue(body["connection"]["verified"])
        stored = json.loads(self.secret_data["google_oauth_tokens:google_calendar"])
        self.assertEqual(stored["access_token"], "access-1")
        self.assertEqual(stored["refresh_token"], "refresh-1")

    def test_callback_with_invalid_state_returns_400_and_leaves_connection_unchanged(self):
        response = self.client.post(
            "/setup/connections/google_calendar/callback",
            json={"code": "valid-code", "state": "invalid-state"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.config_data["external_connections"], {})
        self.assertNotIn("google_oauth_tokens:google_calendar", self.secret_data)

    def test_disconnect_clears_tokens_and_marks_connection_disconnected(self):
        self.config_data["external_connections"] = {
            "google_calendar": {
                "configured": True,
                "verified": True,
                "available": True,
            }
        }
        self.secret_data["google_oauth_tokens:google_calendar"] = json.dumps(
            {"access_token": "access-1", "refresh_token": "refresh-1"}
        )

        response = self.client.post("/setup/connections/google_calendar/disconnect")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["connection"]["configured"])
        self.assertFalse(body["connection"]["verified"])
        self.assertNotIn("google_oauth_tokens:google_calendar", self.secret_data)

    def test_gmail_authorize_returns_auth_url_with_gmail_scopes(self):
        payload = self._authorize("gmail")

        query = self._extract_query(payload["auth_url"])
        scope = query["scope"][0]
        self.assertIn("https://www.googleapis.com/auth/gmail.compose", scope)
        self.assertIn("https://www.googleapis.com/auth/gmail.readonly", scope)

    def test_calendar_authorize_returns_auth_url_with_calendar_scope(self):
        payload = self._authorize("google_calendar")

        query = self._extract_query(payload["auth_url"])
        self.assertIn("https://www.googleapis.com/auth/calendar", query["scope"][0])

    def test_state_token_expires_after_ten_minutes(self):
        with patch.object(oauth, "_now", return_value=1_000):
            authorize_payload = self._authorize("google_calendar")
        state = self._extract_query(authorize_payload["auth_url"])["state"][0]

        with patch.object(oauth, "_now", return_value=1_601):
            response = self.client.post(
                "/setup/connections/google_calendar/callback",
                json={"code": "valid-code", "state": state},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.config_data["external_connections"], {})

    def test_authorize_generates_unique_state_tokens(self):
        first = self._authorize("google_calendar")
        second = self._authorize("google_calendar")

        first_state = self._extract_query(first["auth_url"])["state"][0]
        second_state = self._extract_query(second["auth_url"])["state"][0]
        self.assertNotEqual(first_state, second_state)


if __name__ == "__main__":
    unittest.main()
