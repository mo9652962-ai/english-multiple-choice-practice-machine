"""AI 智能推题 (v2.29) — 练题狗式: 基于薄弱分析 + 错题 + 词汇自动推荐
规则引擎: 找出薄弱题型 → 推荐未练过的题 + 高频错题重做 + 生词语境
"""
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


def _trim(text: str, n: int = 80) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[:n] + "…"


@router.get("/ai")
def ai_recommend(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
):
    """AI 智能推题: 薄弱题型出题 + 错题重做 + 生词推送"""
    profile_id = get_active_profile_id(connection)
    user_id = _current_user_id(user)

    # ① 薄弱题型: 正确率最低且有练习记录的题型
    ability = connection.execute(
        """SELECT u.unit_type,
                  SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
                  COUNT(*) total
           FROM practice_answers pa
           JOIN questions q ON q.id = pa.question_id
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND p.profile_id = ? AND p.deleted_at IS NULL
           GROUP BY u.unit_type HAVING COUNT(*) >= 2
           ORDER BY (SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) ASC""",
        (user_id, profile_id),
    ).fetchall()
    weak_type = None
    if ability:
        weakest = ability[0]
        rate = weakest["correct"] / weakest["total"] if weakest["total"] else 0
        if rate < 0.7:
            weak_type = weakest["unit_type"]

    label_map = {"cloze": "完形", "reading": "阅读", "paragraph_matching": "PartB",
                 "part_b": "PartB", "listening": "听力"}

    # ② 推荐题目: 薄弱题型中未做过/错过的题 (取 3)
    recommended_questions = []
    if weak_type:
        rows = connection.execute(
            """SELECT q.id, q.stem, q.question_type, u.title
               FROM questions q
               JOIN units u ON u.id = q.unit_id
               JOIN papers p ON p.id = u.paper_id
               WHERE p.profile_id = ? AND p.deleted_at IS NULL AND u.unit_type = ?
                 AND q.id NOT IN (
                     SELECT pa.question_id FROM practice_answers pa
                     JOIN practice_sessions ps ON ps.id = pa.session_id
                     WHERE ps.user_id IS ?)
               ORDER BY RANDOM() LIMIT 3""",
            (profile_id, weak_type, user_id),
        ).fetchall()
        if rows:
            recommended_questions = [{
                "id": r["id"], "prompt": _trim(r["stem"]),
                "question_type": r["question_type"], "unit_title": r["title"],
            } for r in rows]

    # ③ 高频错题重做 (错 2 次以上)
    redo_wrong = connection.execute(
        """SELECT q.id, q.stem, ws.wrong_count, u.title
           FROM wrong_stats ws
           JOIN questions q ON q.id = ws.question_id
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           WHERE ws.user_id IS ? AND p.profile_id = ? AND p.deleted_at IS NULL AND ws.wrong_count >= 2
           ORDER BY ws.wrong_count DESC, ws.last_wrong_at DESC LIMIT 3""",
        (user_id, profile_id),
    ).fetchall()
    redo_items = [{"id": r["id"], "prompt": _trim(r["stem"]),
                   "wrong_count": r["wrong_count"], "unit_title": r["title"]} for r in redo_wrong]

    # ④ 生词推送: 最近收集但还没掌握的词 (3 个)
    vocab = connection.execute(
        """SELECT id, term, common_meaning FROM vocabulary_entries
           WHERE user_id IS ? AND study_status = 'learning'
           ORDER BY last_reviewed_at IS NULL DESC, id DESC LIMIT 3""",
        (user_id,),
    ).fetchall()
    vocab_items = [{"id": r["id"], "term": r["term"],
                    "meaning": _trim(r["common_meaning"], 40)} for r in vocab]
    if not vocab_items:
        vocab_items = [{"id": r["id"], "term": r["term"],
                        "meaning": _trim(r["common_meaning"], 40)} for r in connection.execute(
            """SELECT id, term, common_meaning FROM vocabulary_entries
               WHERE user_id IS ? AND study_status = 'new' AND translation_status = 'ready'
               ORDER BY id LIMIT 3""", (user_id,)).fetchall()]

    # ⑤ AI 策略文本
    strategy = []
    if weak_type:
        strategy.append(f"📌 你的{label_map.get(weak_type, weak_type)}正确率偏低（{ability[0]['correct']}/{ability[0]['total']}），建议先专项强化")
    if redo_items:
        strategy.append(f"🔁 {len(redo_items)} 道高频错题等待重做，二刷巩固记忆效果最佳")
    if vocab_items:
        strategy.append(f"📖 {len(vocab_items)} 个生词待掌握，建议今天完成词书任务")
    if not strategy:
        strategy.append("🌟 各题型表现均衡，建议进入模拟考试检验综合能力")

    return {
        "weak_type": weak_type,
        "weak_label": label_map.get(weak_type, weak_type) if weak_type else None,
        "questions": recommended_questions,
        "redo": redo_items,
        "vocab": vocab_items,
        "strategy": strategy,
        "source": "rule-engine",
    }