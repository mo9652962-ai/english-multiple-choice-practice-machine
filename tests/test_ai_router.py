from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.services.ai_router import (
    QuotaExceeded,
    _health_cache,
    chat_with_routing,
    check_daily_quota,
)


class AiRouterQuotaTests(unittest.TestCase):
    def test_daily_quota_counts_task_attempts_for_a_user(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    user_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            connection.execute(
                "INSERT INTO ai_usage (task, provider, model, user_id, created_at) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
                ("speaking_practice", "test", "test-model", 7),
            )
            connection.commit()
            with self.assertRaises(QuotaExceeded):
                check_daily_quota(connection, 7, "deep_explain", quota=1)
            self.assertFalse(connection.in_transaction)
        finally:
            connection.close()


class AiRouterCacheTests(unittest.TestCase):
    def test_router_checks_quota_once_for_one_provider_call(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE ai_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    default_model TEXT NOT NULL DEFAULT 'test-model',
                    temperature REAL NOT NULL DEFAULT 0.2,
                    max_tokens INTEGER NOT NULL DEFAULT 1000,
                    task_tags TEXT NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE ai_response_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    task TEXT NOT NULL,
                    user_id INTEGER,
                    profile_id INTEGER,
                    model TEXT NOT NULL DEFAULT '',
                    response TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    user_id INTEGER,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'ok',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO ai_profiles
                    (id, name, base_url, task_tags, priority)
                VALUES (1, 'test-provider', 'http://test.invalid/v1',
                        '["deep_explain"]', 1);
                """
            )
            _health_cache.clear()
            with patch(
                "backend.app.services.ai_router.check_daily_quota",
                autospec=True,
            ) as quota_check, patch(
                "backend.app.services.ai_router.chat_completion",
                return_value='{"ok":true}',
            ):
                result = chat_with_routing(
                    connection,
                    "deep_explain",
                    [{"role": "user", "content": "same input"}],
                    response_format={"type": "json_object"},
                    user_id=7,
                )
            self.assertEqual(result, '{"ok":true}')
            quota_check.assert_called_once_with(connection, 7, "deep_explain")
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_cacheable_task_reuses_local_structured_result(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE ai_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    default_model TEXT NOT NULL DEFAULT 'test-model',
                    temperature REAL NOT NULL DEFAULT 0.2,
                    max_tokens INTEGER NOT NULL DEFAULT 1000,
                    task_tags TEXT NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE ai_response_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    task TEXT NOT NULL,
                    user_id INTEGER,
                    profile_id INTEGER,
                    model TEXT NOT NULL DEFAULT '',
                    response TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    user_id INTEGER,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'ok',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO ai_profiles
                    (id, name, base_url, task_tags, priority)
                VALUES (1, 'test-provider', 'http://test.invalid/v1',
                        '["deep_explain"]', 1);
                """
            )
            _health_cache.clear()
            messages = [{"role": "user", "content": "same input"}]
            with patch(
                "backend.app.services.ai_router.chat_completion",
                return_value='{"ok":true}',
            ) as mocked:
                first = chat_with_routing(
                    connection,
                    "deep_explain",
                    messages,
                    response_format={"type": "json_object"},
                )
                second = chat_with_routing(
                    connection,
                    "deep_explain",
                    messages,
                    response_format={"type": "json_object"},
                )
            self.assertEqual(first, second)
            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(
                connection.execute("SELECT hit_count FROM ai_response_cache").fetchone()[0],
                1,
            )
            statuses = {
                row[0]
                for row in connection.execute("SELECT status FROM ai_usage").fetchall()
            }
            self.assertEqual(statuses, {"ok", "cached"})
        finally:
            connection.close()

    def test_invalid_structured_response_uses_next_profile(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE ai_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    default_model TEXT NOT NULL DEFAULT 'test-model',
                    temperature REAL NOT NULL DEFAULT 0.2,
                    max_tokens INTEGER NOT NULL DEFAULT 1000,
                    task_tags TEXT NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE ai_response_cache (
                    cache_key TEXT NOT NULL UNIQUE,
                    task TEXT NOT NULL,
                    user_id INTEGER,
                    profile_id INTEGER,
                    model TEXT NOT NULL DEFAULT '',
                    response TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    user_id INTEGER,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'ok',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO ai_profiles (id, name, base_url, task_tags, priority)
                VALUES
                    (1, 'primary', 'http://primary.invalid/v1', '["deep_explain"]', 1),
                    (2, 'fallback', 'http://fallback.invalid/v1', '["deep_explain"]', 2);
                """
            )
            _health_cache.clear()
            with patch(
                "backend.app.services.ai_router.chat_completion",
                side_effect=["not-json", '{"ok":true}'],
            ) as mocked:
                result = chat_with_routing(
                    connection,
                    "deep_explain",
                    [{"role": "user", "content": "same input"}],
                    response_format={"type": "json_object"},
                )
            self.assertEqual(result, '{"ok":true}')
            self.assertEqual(mocked.call_count, 2)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM ai_usage WHERE status = 'fallback'"
                ).fetchone()[0],
                1,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
