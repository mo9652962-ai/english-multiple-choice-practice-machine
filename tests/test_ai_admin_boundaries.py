from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.app.routers.ai import (
    AiModelListRequest,
    AiModelsVisibilityUpdate,
    AiModelVisibilityUpdate,
    AiProfileTestRequest,
    read_available_models,
    set_all_model_visibility,
    set_model_visibility,
    sync_profile_models,
    test_connection as ai_test_connection,
    test_profile as ai_test_profile,
)


class AiAdminBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")

    def tearDown(self) -> None:
        self.connection.close()

    def test_non_admin_is_rejected_before_external_model_calls(self) -> None:
        non_admin = {"id": 101, "is_admin": False}
        with (
            patch("backend.app.routers.auth.AUTH_ENABLED", True),
            patch("backend.app.routers.ai.list_available_models") as list_models,
            self.assertRaises(HTTPException) as raised,
        ):
            read_available_models(
                AiModelListRequest(base_url="https://example.invalid"),
                self.connection,
                non_admin,
            )
        self.assertEqual(raised.exception.status_code, 403)
        list_models.assert_not_called()

    def test_management_endpoints_have_admin_dependency_parameters(self) -> None:
        for endpoint in (
            ai_test_connection,
            sync_profile_models,
            set_model_visibility,
            set_all_model_visibility,
            ai_test_profile,
        ):
            dependency_names = {
                parameter.name
                for parameter in __import__("inspect").signature(endpoint).parameters.values()
            }
            self.assertIn("user", dependency_names, endpoint.__name__)


if __name__ == "__main__":
    unittest.main()
