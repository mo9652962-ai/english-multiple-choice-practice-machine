from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.services.agent_runtime import _call_agent_llm, _fallback_plan


class AgentFallbackPlanTests(unittest.TestCase):
    def test_wrong_and_weak_findings_create_safe_review_actions(self) -> None:
        actions = _fallback_plan(
            {
                "findings": [
                    {"type": "wrong_questions"},
                    {"type": "weak_type"},
                ]
            }
        )
        self.assertEqual(
            [item["type"] for item in actions],
            ["GENERATE_REPORT", "RECOMMEND_QUESTIONS"],
        )

    def test_empty_findings_keep_auditable_encouragement(self) -> None:
        actions = _fallback_plan({"findings": []})
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "ENCOURAGE")


class AgentRoutingTests(unittest.TestCase):
    def test_agent_llm_uses_task_router_and_structured_output(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            with patch(
                "backend.app.services.agent_runtime.chat_with_routing",
                return_value='{"status":"ok","findings":[]}',
            ) as routed:
                result = _call_agent_llm(
                    connection,
                    "agent_analyze",
                    [{"role": "user", "content": "{}"}],
                    user_id=7,
                )

            self.assertEqual(result["status"], "ok")
            routed.assert_called_once()
            self.assertEqual(routed.call_args.args[1], "agent_analyze")
            self.assertEqual(routed.call_args.kwargs["user_id"], 7)
            self.assertEqual(
                routed.call_args.kwargs["response_format"],
                {"type": "json_object"},
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
