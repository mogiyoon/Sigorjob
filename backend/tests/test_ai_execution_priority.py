import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.agent import PLANNING_CAPABILITIES_PROMPT, SYSTEM_PROMPT


class AIExecutionPriorityPromptTests(unittest.TestCase):
    def test_system_prompt_contains_execution_priority_instruction(self):
        self.assertIn("prefer direct api calls over opening links", SYSTEM_PROMPT.lower())

    def test_system_prompt_lists_priority_order(self):
        self.assertIn(
            "direct api > mcp tool > connector plugin > link handoff",
            SYSTEM_PROMPT.lower(),
        )

    def test_system_prompt_rejects_link_only_plans_when_helper_exists(self):
        self.assertIn(
            "do not open a link when a helper tool can complete the action directly",
            SYSTEM_PROMPT.lower(),
        )

    def test_system_prompt_mentions_calendar_helper_for_calendar_requests(self):
        prompt = f"{SYSTEM_PROMPT}\n{PLANNING_CAPABILITIES_PROMPT}".lower()
        self.assertIn("calendar_helper", prompt)
        self.assertIn("calendar", prompt)

    def test_system_prompt_mentions_gmail_or_draft_helper_for_email_requests(self):
        prompt = f"{SYSTEM_PROMPT}\n{PLANNING_CAPABILITIES_PROMPT}".lower()
        self.assertIn("mcp gmail", prompt)
        self.assertIn("draft_helper", prompt)
        self.assertIn("mailto", prompt)


if __name__ == "__main__":
    unittest.main()
