import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.secret_store import secret_store
from config.store import config_store
from connections import oauth
from connections.drivers.google_calendar import GoogleCalendarConnectorDriver


class GoogleOAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_data = {
            "google_oauth_client_id": "client-id",
            "google_oauth_client_secret": "client-secret",
            "google_oauth_redirect_uri": "http://localhost/oauth/callback",
        }
        self.secret_data = {}
        self.config_set_calls = []
        self._orig_config_get = config_store.get
        self._orig_config_set = config_store.set
        self._orig_secret_get = secret_store.get
        self._orig_secret_set = secret_store.set
        config_store.get = lambda key, default=None: self.config_data.get(key, default)
        config_store.set = lambda key, value: self.config_set_calls.append((key, value))
        secret_store.get = lambda key: self.secret_data.get(key)
        secret_store.set = lambda key, value: (self.secret_data.__setitem__(key, value) or True, None)

    async def asyncTearDown(self):
        config_store.get = self._orig_config_get
        config_store.set = self._orig_config_set
        secret_store.get = self._orig_secret_get
        secret_store.set = self._orig_secret_set

    async def test_oauth_token_exchange_returns_and_stores_tokens(self):
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
            result = await oauth.exchange_code_for_tokens("google_calendar", "auth-code")

        self.assertTrue(result["success"])
        assert result["data"] is not None
        self.assertEqual(result["data"]["access_token"], "access-1")
        self.assertEqual(result["data"]["refresh_token"], "refresh-1")
        stored = oauth.get_stored_tokens("google_calendar")
        assert stored is not None
        self.assertEqual(stored["access_token"], "access-1")
        self.assertEqual(stored["refresh_token"], "refresh-1")

    async def test_oauth_token_refresh_returns_new_access_token(self):
        await oauth.store_tokens(
            "google_calendar",
            {
                "access_token": "stale-token",
                "refresh_token": "refresh-1",
                "expires_at": 1,
            },
        )
        with patch.object(
            oauth,
            "_post_form",
            return_value={
                "access_token": "fresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        ):
            result = await oauth.refresh_access_token("google_calendar")

        self.assertTrue(result["success"])
        assert result["data"] is not None
        self.assertEqual(result["data"]["access_token"], "fresh-token")
        self.assertEqual(result["data"]["refresh_token"], "refresh-1")

    async def test_oauth_token_is_saved_via_secret_store_only(self):
        with patch.object(
            oauth,
            "_post_form",
            return_value={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
            },
        ):
            result = await oauth.exchange_code_for_tokens("gmail", "auth-code")

        self.assertTrue(result["success"])
        self.assertEqual(self.config_set_calls, [])
        self.assertIn("google_oauth_tokens:gmail", self.secret_data)

    async def test_calendar_create_event_with_mocked_api_returns_event_details(self):
        driver = GoogleCalendarConnectorDriver()
        connection = {
            "id": "google_calendar",
            "driver_id": "google_calendar",
            "configured": True,
            "verified": True,
            "capabilities": ["create_calendar_event"],
        }
        with patch.object(oauth, "get_access_token", return_value="access-token"), patch.object(
            driver,
            "_create_calendar_event",
            return_value={"id": "event-123", "htmlLink": "https://calendar.google.com/event?eid=123"},
        ):
            result = await driver.execute(
                connection,
                "create_calendar_event",
                {
                    "title": "합주",
                    "details": "테스트",
                    "dates": "20260401T080000Z/20260401T090000Z",
                },
            )

        self.assertTrue(result.success)
        self.assertTrue(result.handled)
        assert result.data is not None
        self.assertEqual(result.data["event_id"], "event-123")
        self.assertEqual(result.data["event_link"], "https://calendar.google.com/event?eid=123")

    async def test_calendar_create_event_falls_back_to_template_link_without_token(self):
        driver = GoogleCalendarConnectorDriver()
        connection = {
            "id": "google_calendar",
            "driver_id": "google_calendar",
            "configured": True,
            "verified": True,
            "capabilities": ["create_calendar_event"],
        }
        with patch.object(oauth, "get_access_token", return_value=None):
            result = await driver.execute(
                connection,
                "create_calendar_event",
                {
                    "title": "합주",
                    "details": "테스트",
                    "dates": "20260401T080000Z/20260401T090000Z",
                },
            )

        self.assertTrue(result.success)
        self.assertTrue(result.handled)
        assert result.data is not None
        self.assertIn("calendar.google.com/calendar/render?action=TEMPLATE", result.data["url"])


if __name__ == "__main__":
    unittest.main()
