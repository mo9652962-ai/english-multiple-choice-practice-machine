from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.routers.agent import AgentRunRequest, create_run


class AgentRouterSecurityTests(unittest.TestCase):
    def test_client_user_id_cannot_override_authenticated_scope(self) -> None:
        connection = sqlite3.connect(":memory:")
        with patch(
            "backend.app.routers.agent.run_learning_agent",
            return_value={"run_id": 1, "status": "completed"},
        ) as run_agent:
            create_run(
                AgentRunRequest(user_id=202, goal="review"),
                connection,
                {"id": 101},
            )
        self.assertEqual(run_agent.call_args.args[0], 101)
        connection.close()

    def test_client_user_id_is_ignored_in_local_mode(self) -> None:
        connection = sqlite3.connect(":memory:")
        with patch(
            "backend.app.routers.agent.run_learning_agent",
            return_value={"run_id": 1, "status": "completed"},
        ) as run_agent:
            create_run(
                AgentRunRequest(user_id=202, goal="review"),
                connection,
                None,
            )
        self.assertIsNone(run_agent.call_args.args[0])
        connection.close()


if __name__ == "__main__":
    unittest.main()
