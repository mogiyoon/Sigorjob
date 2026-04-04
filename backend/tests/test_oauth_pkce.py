import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.secret_store import secret_store
from config.store import config_store
from connections import oauth
from gateway.routes.setup import router as setup_router


class OAuthPkceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
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

    async def asyncTearDown(self):
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

    async def test_generate_pkce_pair_returns_valid_verifier_and_challenge(self):
        verifier, challenge = oauth.generate_pkce_pair()

        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertRegex(verifier, r"^[A-Za-z0-9\-._~]+$")
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        self.assertEqual(challenge, expected)

    async def test_authorize_returns_auth_url_with_pkce_challenge_and_without_client_secret(self):
        payload = self._authorize("google_calendar")

        query = self._extract_query(payload["auth_url"])
        self.assertIn("code_challenge", query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("client_secret", query)

    async def test_callback_sends_code_verifier_without_client_secret_and_cleans_up_state(self):
        authorize_payload = self._authorize("google_calendar")
        state = self._extract_query(authorize_payload["auth_url"])["state"][0]
        stored_verifier = str(oauth._oauth_states[state]["code_verifier"])

        post_form = AsyncMock(
            return_value={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        with patch.object(oauth, "_post_form", post_form):
            response = self.client.post(
                "/setup/connections/google_calendar/callback",
                json={"code": "valid-code", "state": state},
            )

        self.assertEqual(response.status_code, 200)
        request_data = post_form.await_args.args[1]
        self.assertEqual(request_data["code_verifier"], stored_verifier)
        self.assertNotIn("client_secret", request_data)
        self.assertNotIn(state, oauth._oauth_states)

    async def test_refresh_uses_client_id_without_client_secret(self):
        await oauth.store_tokens(
            "google_calendar",
            {
                "access_token": "stale-token",
                "refresh_token": "refresh-1",
                "expires_at": 1,
            },
        )

        post_form = AsyncMock(
            return_value={
                "access_token": "fresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        with patch.object(oauth, "_post_form", post_form):
            result = await oauth.refresh_access_token("google_calendar")

        self.assertTrue(result["success"])
        request_data = post_form.await_args.args[1]
        self.assertEqual(request_data["client_id"], "client-id")
        self.assertNotIn("client_secret", request_data)

    async def test_old_client_secret_config_is_ignored_when_pkce_is_used(self):
        authorize_payload = self._authorize("google_calendar")
        query = self._extract_query(authorize_payload["auth_url"])
        state = query["state"][0]

        post_form = AsyncMock(
            return_value={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        with patch.object(oauth, "_post_form", post_form):
            response = self.client.post(
                "/setup/connections/google_calendar/callback",
                json={"code": "valid-code", "state": state},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("client_secret", query)
        self.assertNotIn("client_secret", post_form.await_args.args[1])
        stored = json.loads(self.secret_data["google_oauth_tokens:google_calendar"])
        self.assertEqual(stored["access_token"], "access-1")


if __name__ == "__main__":
    unittest.main()
