"""错题知识点归因分析 API（v3.0）。

POST /api/wrong/analysis/run              —— 运行归因分析（12 分类 → 知识点 → 建议 → 趋势）
GET  /api/wrong/analysis/report/{id}      —— 读取单份归因报告（含逐题明细）
GET  /api/wrong/analysis/history          —— 历史归因分析列表
GET  /api/wrong/analysis/trend            —— 趋势追踪（近 N 次快照序列 + 掌握度档案）
GET  /api/wrong/analysis/knowledge-points —— 知识点累计统计
GET  /api/wrong/analysis/suggestions      —— 最新（或指定）报告的学习建议
GET  /api/wrong/analysis/meta             —— 12 分类与知识点目录（前端图例用）
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.wrong_analysis import (
    CAUSE_LABELS,
    KNOWLEDGE_POINT_CATALOG,
    build_learning_suggestions,
    get_cause_trend,
    get_knowledge_point_stats,
    list_analysis_history,
    load_analysis_report,
    run_attribution_analysis,
)

router = APIRouter(prefix="/wrong/analysis", tags=["wrong-analysis"])


class AttributionRunRequest(BaseModel):
    question_ids: list[int] = Field(default_factory=list)
    scope_title: str = ""
    scope_key: str = ""
    unit_ids: list[int] = Field(default_factory=list)
    with_ai_report: bool = True


@router.post("/run")
def run_analysis(
    request: AttributionRunRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """运行一次完整归因分析。

    - question_ids 为空时自动选取当前高频错题（错 ≥3 次或手动标记，至多 20 道）；
    - 归因、聚合、知识点、建议、趋势全部落库，返回完整结构化结果；
    - with_ai_report=False 跳过 AI 匿名总结（纯本地，速度快，适合批量补数据）。
    """
    question_ids = request.question_ids
    if not question_ids:
        question_ids = [
            int(row["question_id"])
            for row in connection.execute(
                """
                SELECT question_id FROM wrong_stats
                WHERE wrong_count >= 3 OR manually_frequent = 1
                ORDER BY wrong_count DESC, last_wrong_at DESC
                LIMIT 20
                """
            ).fetchall()
        ]
    if not question_ids:
        raise HTTPException(status_code=400, detail="没有可分析的错题")
    try:
        result = run_attribution_analysis(
            connection,
            question_ids,
            scope_title=request.scope_title,
            scope_key=request.scope_key,
            unit_ids=request.unit_ids,
            with_ai_report=request.with_ai_report,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:  # AI 网络/解析异常统一转 400，避免 500 噪音
        raise HTTPException(status_code=400, detail=f"归因分析失败：{error}") from error
    # streak 学习行为记录（失败不阻塞）
    try:
        from ..services.streak import record_activity

        record_activity(connection, "wrong_attribution", f"report {result['report_id']}")
    except Exception:
        pass
    return result


@router.get("/report/{report_id}")
def get_report(
    report_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    report = load_analysis_report(connection, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="归因分析报告不存在")
    return report


@router.get("/history")
def get_history(
    limit: int = 20,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    return {
        "items": list_analysis_history(connection, limit=min(limit, 50)),
    }


@router.get("/trend")
def get_trend(
    limit: int = 8,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """趋势追踪：近 N 次报告的 12 分类快照序列 + 掌握度档案 + 显著变化。"""
    return get_cause_trend(connection, limit=min(limit, 20))


@router.get("/knowledge-points")
def get_knowledge_points(
    limit: int = 20,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    return {
        "items": get_knowledge_point_stats(connection, limit=min(limit, 50)),
    }


@router.get("/suggestions")
def get_suggestions(
    report_id: int | None = None,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """学习建议：report_id 缺省时取最近一份含逐题明细的归因报告。"""
    if report_id is None:
        row = connection.execute(
            """
            SELECT r.id, r.aggregate_data
            FROM wrong_analysis_reports r
            WHERE EXISTS (
                SELECT 1 FROM wrong_cause_diagnoses d WHERE d.report_id = r.id
            )
            ORDER BY r.id DESC LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="还没有归因分析记录，请先运行一次分析")
        report_id = int(row["id"])
    else:
        row = connection.execute(
            "SELECT aggregate_data FROM wrong_analysis_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="归因分析报告不存在")
    try:
        import json as _json

        aggregate = _json.loads(row["aggregate_data"] or "{}")
    except Exception:
        aggregate = {}
    return build_learning_suggestions(connection, int(report_id), aggregate)


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """12 分类目录 + 知识点白名单（前端图例/筛选无需另发请求拉字典）。"""
    return {
        "causes": [
            {"code": code, "label": label} for code, label in CAUSE_LABELS.items()
        ],
        "knowledge_points": {
            cause: [
                {"code": point["code"], "label": point["label"]}
                for point in points
            ]
            for cause, points in KNOWLEDGE_POINT_CATALOG.items()
        },
    }
