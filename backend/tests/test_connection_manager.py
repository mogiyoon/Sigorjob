import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connections import manager as connection_manager


class ConnectionManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_find_calendar_connection_when_permissions_and_connection_are_ready(self):
        connection = {
            "id": "google_calendar",
            "driver_id": "google_calendar",
            "configured": True,
            "verified": True,
            "available": True,
            "capabilities": ["create_calendar_event"],
            "required_permissions": ["external_connection_access", "calendar_event_creation"],
            "capability_permissions": {"create_calendar_event": ["calendar_event_creation"]},
        }
        with patch.object(connection_manager, "list_connections", return_value=[connection]), patch.object(
            connection_manager,
            "_granted_permissions",
            return_value={"external_connection_access", "calendar_event_creation"},
        ):
            resolved = await connection_manager.find_connection_for_capability("create_calendar_event")
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved["id"], "google_calendar")

    async def test_template_connector_can_handle_calendar_capability(self):
        connection = {
            "id": "shared_calendar",
            "driver_id": "template_connector",
            "configured": True,
            "verified": True,
            "available": True,
            "capabilities": ["create_calendar_event"],
            "required_permissions": ["external_connection_access"],
            "capability_permissions": {"create_calendar_event": ["calendar_event_creation"]},
            "metadata": {
                "templates": {
                    "create_calendar_event": {
                        "url_template": "https://calendar.example.com/new?title={title}&dates={dates}",
                        "title_template": "{title} 일정 만들기",
                    }
                }
            },
        }
        with patch.object(connection_manager, "list_connections", return_value=[connection]), patch.object(
            connection_manager,
            "_granted_permissions",
            return_value={"external_connection_access", "calendar_event_creation"},
        ):
            result = await connection_manager.execute_capability(
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
            self.assertIn("calendar.example.com", result.data["url"])

    async def test_execute_capability_returns_unhandled_without_ready_connection(self):
        with patch.object(connection_manager, "list_connections", return_value=[]), patch.object(
            connection_manager,
            "_granted_permissions",
            return_value=set(),
        ):
            result = await connection_manager.execute_capability(
                "create_calendar_event",
                {
                    "title": "합주",
                    "details": "테스트",
                    "dates": "20260401T080000Z/20260401T090000Z",
                },
            )
            self.assertFalse(result.success)
            self.assertFalse(result.handled)


if __name__ == "__main__":
    unittest.main()
