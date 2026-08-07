"""词汇量自测 (v2.33, 百词斩式借鉴) — 抽样判断 → 估算词汇量
取 10 词 (已学+生词混合) → 认识/模糊/不认识 → 线性估算
"""
from __future__ import annotations

import random
import sqlite3
from fastapi import APIRouter, Depends

from ..database import get_db

router = APIRouter(prefix="/api/vocab/quiz", tags=["vocab-quiz"])

# 估算基数 (按题库词库规模)
BASE_VOCAB = 8000


@router.get("")
def get_quiz(
    count: int = 10,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """取 count 个词做词汇量抽样 (已学/生词按库内比例)"""
    count = max(5, min(count, 20))
    total = connection.execute("SELECT COUNT(*) FROM vocabulary_entries").fetchone()[0]
    learned = connection.execute(
        "SELECT COUNT(*) FROM vocabulary_entries WHERE COALESCE(study_status,'') IN ('mastered','learning')"
    ).fetchone()[0]
    # 按比例抽样: 已学词为主 + 少量生词
    n_learned = max(2, int(count * 0.6))
    n_new = count - n_learned
    items: list[dict] = []
    for sql, n in [
        ("SELECT id, term AS word, phonetic, COALESCE(common_meaning, contextual_meaning,'') AS meaning "
         "FROM vocabulary_entries WHERE COALESCE(study_status,'') IN ('mastered','learning') ORDER BY RANDOM() LIMIT ?", n_learned),
        ("SELECT id, term AS word, phonetic, COALESCE(common_meaning, contextual_meaning,'') AS meaning "
         "FROM vocabulary_entries WHERE COALESCE(study_status,'') NOT IN ('mastered','learning') ORDER BY RANDOM() LIMIT ?", n_new),
    ]:
        for r in connection.execute(sql, (n,)).fetchall():
            items.append(dict(r))
    random.shuffle(items)
    return {
        "items": items,
        "total": len(items),
        "estimate_base": BASE_VOCAB,
        "learned_count": learned,
        "total_count": total,
    }


@router.post("/estimate")
def estimate_quiz(
    payload: dict,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """根据答题结果估算词汇量
    payload: {results: [{word, known: 0|1|2}]}  0=不认识 1=模糊 2=认识
    """
    results = payload.get("results") or []
    if not results:
        return {"estimated": 0, "detail": "无数据"}
    # 加权: 认识=1.0 模糊=0.5 不认识=0
    score = sum({"2": 1.0, "1": 0.5, "0": 0.0}.get(str(r.get("known", 0)), 0.0) for r in results)
    ratio = score / len(results)
    estimated = int(BASE_VOCAB * ratio)
    # 学习过但没答对 → 打折 (低于 3 成 → 认为词汇量偏低)
    if ratio < 0.3:
        estimated = int(estimated * 0.7)
    return {
        "estimated": estimated,
        "ratio": round(ratio, 2),
        "answered": len(results),
        "level": (
            "初阶 (<1500)" if estimated < 1500
            else "进阶 (1500-4000)" if estimated < 4000
            else "高阶 (4000-7000)" if estimated < 7000
            else "大师级 (7000+)"
        ),
    }
