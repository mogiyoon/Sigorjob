import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connections.drivers.gmail import GmailConnectorDriver
from connections import oauth


class GmailDriverTests(unittest.IsolatedAsyncioTestCase):
    async def test_gmail_send_email_with_mocked_api_returns_message_id(self):
        driver = GmailConnectorDriver()
        connection = {
            "id": "gmail",
            "driver_id": "gmail",
            "configured": True,
            "verified": True,
            "capabilities": ["send_email", "read_email"],
        }
        with patch.object(oauth, "get_access_token", return_value="access-token"), patch.object(
            driver,
            "_send_email",
            return_value="message-123",
        ):
            result = await driver.execute(
                connection,
                "send_email",
                {"to": "test@example.com", "subject": "hello", "body": "world"},
            )

        self.assertTrue(result.success)
        self.assertTrue(result.handled)
        assert result.data is not None
        self.assertEqual(result.data["message_id"], "message-123")

    async def test_gmail_read_email_with_mocked_api_returns_message_summaries(self):
        driver = GmailConnectorDriver()
        connection = {
            "id": "gmail",
            "driver_id": "gmail",
            "configured": True,
            "verified": True,
            "capabilities": ["send_email", "read_email"],
        }
        messages = [
            {
                "id": "msg-1",
                "subject": "Meeting",
                "from": "sender@example.com",
                "snippet": "Schedule update",
            }
        ]
        with patch.object(oauth, "get_access_token", return_value="access-token"), patch.object(
            driver,
            "_read_email",
            return_value=messages,
        ):
            result = await driver.execute(connection, "read_email", {"max_results": 5})

        self.assertTrue(result.success)
        self.assertTrue(result.handled)
        assert result.data is not None
        self.assertEqual(result.data["messages"], messages)

    async def test_gmail_driver_returns_not_authenticated_when_token_is_missing(self):
        driver = GmailConnectorDriver()
        connection = {
            "id": "gmail",
            "driver_id": "gmail",
            "configured": True,
            "verified": True,
            "capabilities": ["send_email", "read_email"],
        }
        with patch.object(oauth, "get_access_token", return_value=None):
            result = await driver.execute(connection, "send_email", {"to": "test@example.com"})

        self.assertFalse(result.success)
        self.assertTrue(result.handled)
        self.assertEqual(result.error, "not authenticated")


if __name__ == "__main__":
    unittest.main()
