"""墨题 AI 学习智能体运行时：Observe → Analyze → Plan → Execute。"""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from .ai_client import chat_completion, get_ai_profile, parse_json_response
from .ai_router import check_daily_quota, record_user_usage
from .diagnostic_report import build_recommendations, generate_diagnostic_report
from .review import count_due

ALLOWED_ACTIONS = {
    "CREATE_TASK",
    "ADJUST_PLAN",
    "GENERATE_REPORT",
    "RECOMMEND_QUESTIONS",
    "ENCOURAGE",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _collect_wrong(connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total, COALESCE(SUM(wrong_count), 0) AS wrong_count,
               COALESCE(SUM(CASE WHEN wrong_count >= 2 OR manually_frequent = 1 THEN 1 ELSE 0 END), 0) AS frequent
        FROM wrong_stats WHERE user_id IS ?
        """,
        (user_id,),
    ).fetchone()
    by_type = connection.execute(
        """
        SELECT u.unit_type, COUNT(*) AS questions, COALESCE(SUM(ws.wrong_count), 0) AS wrong_count
        FROM wrong_stats ws
        JOIN questions q ON q.id = ws.question_id
        JOIN units u ON u.id = q.unit_id
        WHERE ws.user_id IS ? AND ws.wrong_count > 0
        GROUP BY u.unit_type ORDER BY wrong_count DESC
        LIMIT 12
        """,
        (user_id,),
    ).fetchall()
    return {
        "total": int(row["total"] or 0),
        "wrong_count": int(row["wrong_count"] or 0),
        "frequent": int(row["frequent"] or 0),
        "by_type": [dict(item) for item in by_type],
    }


def _collect_practice(connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any]:
    session = connection.execute(
        "SELECT COUNT(*) AS n FROM practice_sessions WHERE user_id IS ?", (user_id,)
    ).fetchone()["n"]
    row = connection.execute(
        """
        SELECT COUNT(*) AS answered,
               COALESCE(SUM(CASE WHEN pa.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct
        FROM practice_answers pa
        JOIN practice_sessions ps ON ps.id = pa.session_id
        WHERE ps.user_id IS ?
        """,
        (user_id,),
    ).fetchone()
    answered = int(row["answered"] or 0)
    correct = int(row["correct"] or 0)
    today = connection.execute(
        """
        SELECT COUNT(*) AS answered,
               COALESCE(SUM(CASE WHEN pa.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct
        FROM practice_answers pa
        JOIN practice_sessions ps ON ps.id = pa.session_id
        WHERE ps.user_id IS ? AND date(pa.answered_at, 'localtime') = date('now', 'localtime')
        """,
        (user_id,),
    ).fetchone()
    today_sessions = connection.execute(
        """SELECT COUNT(*) AS n FROM practice_sessions
           WHERE user_id IS ? AND date(started_at, 'localtime') = date('now', 'localtime')""",
        (user_id,),
    ).fetchone()["n"]
    return {
        "sessions": int(session or 0),
        "answered": answered,
        "correct": correct,
        "accuracy": round(correct / answered, 4) if answered else 0.0,
        "today_sessions": int(today_sessions or 0),
        "today_answered": int(today["answered"] or 0),
        "today_correct": int(today["correct"] or 0),
    }


def _collect_vocabulary(connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(CASE WHEN study_status = 'learning' THEN 1 ELSE 0 END), 0) AS learning,
               COALESCE(SUM(CASE WHEN study_status = 'mastered' THEN 1 ELSE 0 END), 0) AS mastered,
               COALESCE(SUM(CASE WHEN translation_status = 'ready' THEN 1 ELSE 0 END), 0) AS translated
        FROM vocabulary_entries WHERE user_id IS ?
        """,
        (user_id,),
    ).fetchone()
    return {key: int(rows[key] or 0) for key in ("total", "learning", "mastered", "translated")}


def _collect_weak_analysis(connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT u.unit_type,
               SUM(CASE WHEN pa.is_correct = 1 THEN 1 ELSE 0 END) AS correct,
               COUNT(*) AS total
        FROM practice_answers pa
        JOIN practice_sessions ps ON ps.id = pa.session_id
        JOIN questions q ON q.id = pa.question_id
        JOIN units u ON u.id = q.unit_id
        WHERE ps.user_id IS ?
        GROUP BY u.unit_type HAVING COUNT(*) >= 2
        ORDER BY (SUM(CASE WHEN pa.is_correct = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) ASC
        """,
        (user_id,),
    ).fetchall()
    cause_map = {"cloze": "grammar", "reading": "detail", "listening": "uncertain"}
    categories = []
    weak_types = []
    for row in rows:
        rate = (row["correct"] or 0) / row["total"] if row["total"] else 0
        item = {
            "code": cause_map.get(row["unit_type"], str(row["unit_type"])),
            "label": str(row["unit_type"]),
            "count": int((row["total"] or 0) - (row["correct"] or 0)),
            "percentage": round((1 - rate) * 100, 1),
        }
        categories.append(item)
        if rate < 0.7:
            weak_types.append({"unit_type": row["unit_type"], "accuracy": round(rate, 4), "total": row["total"]})
    aggregate = {"question_count": sum(item["count"] for item in categories), "categories": categories}
    return {
        "weak_types": weak_types[:5],
        "recommendations": build_recommendations(connection, aggregate, limit=3),
        "review_due": int(count_due(connection, user_id)),
    }


def observe(user_id: int | None, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
    """并行汇总错题、练习、词汇和薄弱分析，并单独给出今日完成量。"""
    owns_connection = connection is None
    if connection is None:
        from ..database import connect
        connection = connect()
    try:
        collector_names = ("wrong", "practice", "vocabulary", "weak_analysis")
        # 传入测试/事务连接时保持同一连接顺序执行；生产连接使用独立只读连接并行收集。
        if owns_connection:
            def worker(name: str) -> tuple[str, Any]:
                from ..database import connect
                local = connect()
                try:
                    return name, _collect_by_name(name, local, user_id)
                finally:
                    local.close()
            with ThreadPoolExecutor(max_workers=4) as executor:
                collected = dict(executor.map(worker, collector_names))
        else:
            collected = {name: _collect_by_name(name, connection, user_id) for name in collector_names}
        practice = collected["practice"]
        collected["today"] = {
            "answered": practice["today_answered"],
            "correct": practice["today_correct"],
            "sessions": practice["today_sessions"],
            "date": date.today().isoformat(),
        }
        return {"user_id": user_id, "observed_at": date.today().isoformat(), **collected}
    finally:
        if owns_connection:
            connection.close()


def _collect_by_name(name: str, connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any]:
    return {
        "wrong": _collect_wrong,
        "practice": _collect_practice,
        "vocabulary": _collect_vocabulary,
        "weak_analysis": _collect_weak_analysis,
    }[name](connection, user_id)


def _fallback_analysis(context: dict[str, Any]) -> dict[str, Any]:
    wrong = context.get("wrong") or {}
    weak = (context.get("weak_analysis") or {}).get("weak_types") or []
    findings = [
        {
            "type": "weak_type",
            "title": f"{item.get('unit_type', '题型')}正确率偏低",
            "detail": f"当前正确率约 {float(item.get('accuracy', 0)) * 100:.1f}%，共 {item.get('total', 0)} 题。",
            "priority": "high",
        }
        for item in weak[:3]
    ]
    if wrong.get("wrong_count", 0):
        findings.append({
            "type": "wrong_questions",
            "title": "存在待巩固错题",
            "detail": f"累计错题次数 {wrong.get('wrong_count', 0)}，其中高频错题 {wrong.get('frequent', 0)} 道。",
            "priority": "normal",
        })
    return {
        "status": "fallback",
        "summary": f"规则分析完成：当前有 {wrong.get('total', 0)} 道错题记录，今日完成 {context.get('today', {}).get('answered', 0)} 题。",
        "findings": findings,
    }


def _call_agent_llm(
    connection: sqlite3.Connection,
    task: str,
    messages: list[dict[str, str]],
    *,
    user_id: int | None,
    tier: str,
) -> Any:
    check_daily_quota(connection, user_id, task)
    profile = get_ai_profile(connection)
    # 未配置远程密钥时直接走规则兜底；本机 Ollama 等兼容服务允许无 Key。
    if not profile.get("has_api_key") and not str(profile.get("base_url", "")).lower().startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
        raise ValueError("尚未配置可用的 AI API Key")
    usage: dict[str, int] = {}
    try:
        def call(model: str) -> str:
            return chat_completion(
                connection,
                messages,
                response_format={"type": "json_object"},
                profile_id=int(profile["id"]),
                model=model,
                usage_out=usage,
            )

        # 使用 model_pool 的回调接口，确保每个模型都调用现有 chat_completion。
        from .model_pool import completions_with_fallback
        result = completions_with_fallback(tier, call, connection)  # type: ignore[arg-type]
        record_user_usage(
            connection, user_id, task, profile.get("name", "model-pool"), result["model"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        return parse_json_response(str(result["data"]))
    except Exception as error:
        record_user_usage(connection, user_id, task, profile.get("name", "model-pool"), "", status="fallback", error=str(error))
        raise


def analyze(
    context: dict[str, Any],
    connection: sqlite3.Connection | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """让 LLM 归纳学习状态；调用失败时用错题/薄弱题型规则兜底。"""
    owns_connection = connection is None
    if connection is None:
        from ..database import connect
        connection = connect()
    try:
        messages = [
            {"role": "system", "content": "你是英语学习诊断助手。只根据输入的学习统计输出 JSON，不能编造原题内容。格式：{\"status\":\"ok\",\"summary\":\"...\",\"findings\":[{\"type\":\"...\",\"title\":\"...\",\"detail\":\"...\",\"priority\":\"high|normal|low\"}]}"},
            {"role": "user", "content": _json(context)},
        ]
        try:
            result = _call_agent_llm(connection, "agent_analyze", messages, user_id=user_id, tier="high")
            if not isinstance(result, dict):
                raise ValueError("模型分析结果不是 JSON 对象")
            findings = result.get("findings") if isinstance(result.get("findings"), list) else []
            return {"status": str(result.get("status") or "ok"), "summary": str(result.get("summary") or ""), "findings": findings[:12]}
        except Exception:
            return _fallback_analysis(context)
    finally:
        if owns_connection:
            connection.close()


def _fallback_plan(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    return []


def plan(
    analysis: dict[str, Any],
    connection: sqlite3.Connection | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """让 LLM 生成受白名单约束的行动列表；失败返回空列表。"""
    owns_connection = connection is None
    if connection is None:
        from ..database import connect
        connection = connect()
    try:
        messages = [
            {"role": "system", "content": "你是英语学习计划助手。只输出 JSON 数组，每项格式为 {\"type\":\"CREATE_TASK|ADJUST_PLAN|GENERATE_REPORT|RECOMMEND_QUESTIONS|ENCOURAGE\",\"priority\":\"high|normal|low\",\"reason\":\"...\",\"detail\":\"...\"}。最多 5 项。"},
            {"role": "user", "content": _json(analysis)},
        ]
        try:
            result = _call_agent_llm(connection, "agent_plan", messages, user_id=user_id, tier="low")
            actions = result.get("actions") if isinstance(result, dict) else result
            if not isinstance(actions, list):
                raise ValueError("模型计划结果不是数组")
            clean = []
            for action in actions[:5]:
                if not isinstance(action, dict) or action.get("type") not in ALLOWED_ACTIONS:
                    continue
                clean.append({
                    "type": action["type"],
                    "priority": str(action.get("priority") or "normal")[:20],
                    "reason": str(action.get("reason") or "")[:500],
                    "detail": str(action.get("detail") or "")[:1000],
                })
            return clean
        except Exception:
            return _fallback_plan(analysis)
    finally:
        if owns_connection:
            connection.close()


def _insert_decision(connection: sqlite3.Connection, run_id: int, action: dict[str, Any], status: str = "pending") -> int:
    cursor = connection.execute(
        """INSERT INTO agent_decisions (run_id, action_type, priority, reason, detail, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, action["type"], action.get("priority", "normal"), action.get("reason", ""), action.get("detail", ""), status),
    )
    return int(cursor.lastrowid)


def _execute_action(connection: sqlite3.Connection, action: dict[str, Any], user_id: int | None) -> dict[str, Any]:
    action_type = action["type"]
    if action_type == "RECOMMEND_QUESTIONS":
        from ..routers.ai_recommend import ai_recommend
        return ai_recommend(connection, user={"id": user_id} if user_id is not None else None)
    if action_type == "GENERATE_REPORT":
        rows = connection.execute(
            """
            SELECT DISTINCT ws.question_id FROM wrong_stats ws
            JOIN practice_answers pa ON pa.question_id = ws.question_id
            JOIN practice_sessions ps ON ps.id = pa.session_id
            WHERE ws.user_id IS ? AND ws.wrong_count > 0 AND ps.user_id IS ?
            ORDER BY ws.wrong_count DESC LIMIT 20
            """,
            (user_id, user_id),
        ).fetchall()
        question_ids = [int(row["question_id"]) for row in rows]
        if not question_ids:
            return {"skipped": True, "message": "暂无带作答记录的错题，暂不能生成诊断报告"}
        from ..database import get_active_profile_id
        return generate_diagnostic_report(
            connection, question_ids, profile_id=get_active_profile_id(connection), user_id=user_id
        )
    return {"recorded": True, "message": action.get("detail") or "建议已记录"}


def execute(
    plan: list[dict[str, Any]] | dict[str, Any],
    connection: sqlite3.Connection,
    user_id: int | None,
    *,
    run_id: int | None = None,
) -> list[dict[str, Any]]:
    """执行行动并将决策、工具调用写入 Agent 表。"""
    actions = plan.get("actions", []) if isinstance(plan, dict) else plan
    actions = actions if isinstance(actions, list) else []
    if run_id is None:
        cursor = connection.execute(
            "INSERT INTO agent_runs (user_id, status, started_at) VALUES (?, 'running', CURRENT_TIMESTAMP)",
            (user_id,),
        )
        run_id = int(cursor.lastrowid)
        connection.commit()
    results: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict) or action.get("type") not in ALLOWED_ACTIONS:
            continue
        decision_id = _insert_decision(connection, run_id, action)
        tool_name = action["type"].lower()
        try:
            result = _execute_action(connection, action, user_id)
            connection.execute(
                "UPDATE agent_decisions SET status = 'completed' WHERE id = ?", (decision_id,)
            )
            success = 1
        except Exception as error:
            result = {"error": str(error)}
            connection.execute(
                "UPDATE agent_decisions SET status = 'failed' WHERE id = ?", (decision_id,)
            )
            success = 0
        connection.execute(
            """INSERT INTO agent_tool_calls (run_id, tool_name, args, result, success)
               VALUES (?, ?, ?, ?, ?)""",
            (run_id, tool_name, _json(action), _json(result), success),
        )
        connection.commit()
        results.append({"decision_id": decision_id, "type": action["type"], "success": bool(success), "result": result})
    if not actions and run_id is not None:
        # 保留一次“无行动”的可审计决策，行动列表本身仍严格是空列表。
        note = {"type": "ENCOURAGE", "priority": "low", "reason": "本轮未生成需要执行的行动", "detail": "继续保持学习节奏，积累更多作答记录后再运行智能体"}
        decision_id = _insert_decision(connection, run_id, note, status="skipped")
        connection.execute(
            "INSERT INTO agent_tool_calls (run_id, tool_name, args, result, success) VALUES (?, ?, ?, ?, 1)",
            (run_id, "agent_runtime", _json({}), _json({"decision_id": decision_id, "message": "无行动需要执行"})),
        )
        connection.commit()
        results.append({"decision_id": decision_id, "type": "ENCOURAGE", "success": True, "result": {"skipped": True}})
    return results


def _insert_step(connection: sqlite3.Connection, run_id: int, step_type: str, status: str, input_value: Any, output_value: Any, error: str = "") -> None:
    connection.execute(
        """INSERT INTO agent_steps (run_id, step_type, status, input, output, error)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, step_type, status, _json(input_value), _json(output_value), error[:1000]),
    )
    connection.commit()


def run_learning_agent(
    user_id: int | None,
    connection: sqlite3.Connection | None = None,
    goal: str = "",
) -> dict[str, Any]:
    """执行一次完整四步循环，并返回 run_id 与摘要。"""
    owns_connection = connection is None
    if connection is None:
        from ..database import connect
        connection = connect()
    cursor = connection.execute(
        """INSERT INTO agent_runs (user_id, mode, status, goal, started_at)
           VALUES (?, 'learning', 'running', ?, CURRENT_TIMESTAMP)""",
        (user_id, goal[:500]),
    )
    run_id = int(cursor.lastrowid)
    connection.commit()
    try:
        context = observe(user_id, connection)
        connection.execute("UPDATE agent_runs SET current_step = 1 WHERE id = ?", (run_id,))
        _insert_step(connection, run_id, "observe", "completed", {"user_id": user_id}, context)

        analysis = analyze(context, connection, user_id)
        connection.execute("UPDATE agent_runs SET current_step = 2 WHERE id = ?", (run_id,))
        _insert_step(connection, run_id, "analyze", "completed" if analysis.get("status") == "ok" else "fallback", context, analysis)

        actions = plan(analysis, connection, user_id)
        connection.execute("UPDATE agent_runs SET current_step = 3 WHERE id = ?", (run_id,))
        _insert_step(connection, run_id, "plan", "completed" if actions else "fallback", analysis, actions)

        results = execute(actions, connection, user_id, run_id=run_id)
        connection.execute("UPDATE agent_runs SET current_step = 4 WHERE id = ?", (run_id,))
        _insert_step(connection, run_id, "execute", "completed", actions, results)
        summary = str(analysis.get("summary") or "学习智能体本轮运行完成")
        connection.execute(
            "UPDATE agent_runs SET status = 'completed', summary = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (summary[:2000], run_id),
        )
        connection.commit()
        return {"run_id": run_id, "status": "completed", "summary": summary, "analysis": analysis, "plan": actions, "results": results}
    except Exception as error:
        connection.execute(
            "UPDATE agent_runs SET status = 'failed', error = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(error)[:1000], run_id),
        )
        connection.commit()
        return {"run_id": run_id, "status": "failed", "summary": "智能体运行失败，已保留运行记录", "error": str(error)}
    finally:
        if owns_connection:
            connection.close()
