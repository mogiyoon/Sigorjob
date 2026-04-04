import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import custom_commands


class CustomCommandsTests(unittest.TestCase):
    def setUp(self):
        self.config_data: dict = {}
        self._orig_get = custom_commands.config_store.get
        self._orig_set = custom_commands.config_store.set
        custom_commands.config_store.get = lambda key, default=None: self.config_data.get(key, default)
        custom_commands.config_store.set = lambda key, value: self.config_data.__setitem__(key, value)

    def tearDown(self):
        custom_commands.config_store.get = self._orig_get
        custom_commands.config_store.set = self._orig_set

    def test_match_custom_command_contains_matches_substring(self):
        command = {
            "id": "1",
            "trigger": "launch playlist",
            "match_type": "contains",
            "action_text": "open music",
            "enabled": True,
        }
        self.config_data["custom_commands"] = [command]

        matched = custom_commands.match_custom_command("please launch playlist for me")

        self.assertEqual(matched, command)

    def test_match_custom_command_exact_only_matches_full_string(self):
        command = {
            "id": "1",
            "trigger": "open dashboard",
            "match_type": "exact",
            "action_text": "open app",
            "enabled": True,
        }
        self.config_data["custom_commands"] = [command]

        exact_matched = custom_commands.match_custom_command("open dashboard")
        partial_matched = custom_commands.match_custom_command("please open dashboard")

        self.assertEqual(exact_matched, command)
        self.assertIsNone(partial_matched)

    def test_match_custom_command_returns_none_for_unrelated_command(self):
        self.config_data["custom_commands"] = [
            {
                "id": "1",
                "trigger": "sync calendar",
                "match_type": "contains",
                "action_text": "sync",
                "enabled": True,
            }
        ]

        matched = custom_commands.match_custom_command("play jazz music")

        self.assertIsNone(matched)

    def test_match_custom_command_ignores_disabled_command(self):
        self.config_data["custom_commands"] = [
            {
                "id": "1",
                "trigger": "sync calendar",
                "match_type": "contains",
                "action_text": "sync",
                "enabled": False,
            }
        ]

        matched = custom_commands.match_custom_command("sync calendar now")

        self.assertIsNone(matched)
