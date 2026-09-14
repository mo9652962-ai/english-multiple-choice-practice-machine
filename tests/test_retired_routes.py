from __future__ import annotations

import unittest


class RetiredRouteTests(unittest.TestCase):
    def test_legacy_wrong_analysis_router_remains_importable_and_hidden(self) -> None:
        from backend.app.routers.wrong_analysis import router

        self.assertEqual(router.prefix, "/wrong/analysis")
        self.assertTrue(router.routes)
        self.assertTrue(all(route.include_in_schema is False for route in router.routes))

    def test_legacy_endpoint_returns_explicit_migration_response(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.routers.wrong_analysis import router

        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).get("/wrong/analysis/meta")
        self.assertEqual(response.status_code, 410)


if __name__ == "__main__":
    unittest.main()
