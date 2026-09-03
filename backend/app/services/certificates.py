"""证书服务 — 企业版功能：考试达标自动生成电子证书。

设计：
- 考试交卷时由 exam router 调用 issue_certificate_if_passed()
- 达标线默认 60%（可由组卷 pass_score 覆盖）
- 同一用户同一考试只发一张证书（cert_no 唯一 + 查重）
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime


def _cert_no(exam_id: int, user_id: int, issued_at: str) -> str:
    """生成稳定、防伪的证书编号。"""
    raw = f"EPM-{exam_id}-{user_id}-{issued_at}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"EPM-{user_id}-{exam_id}-{digest}"


def level_for(accuracy: float) -> str:
    if accuracy >= 90:
        return "优秀"
    if accuracy >= 75:
        return "良好"
    return "合格"


def issue_certificate_if_passed(
    connection: sqlite3.Connection,
    *,
    exam_id: int,
    user_id: int | None,
    profile_id: int,
    title: str,
    score: float,
    max_score: float,
    pass_score: float = 60.0,
) -> dict | None:
    """考试达标则生成证书，否则返回 None。重复调用幂等。

    单用户模式（user_id 为 None）时也发证——该用户即唯一使用者，
    证书归属本地账号；多用户模式则归属具体 user_id。
    """
    accuracy = (score / max_score * 100) if max_score else 0
    if accuracy < pass_score:
        return None
    owner = user_id if user_id is not None else 0  # 0 = 单用户本地归属
    # 幂等：同一用户+考试已有证书则直接返回
    existing = connection.execute(
        "SELECT * FROM certificates WHERE exam_id = ? AND user_id = ?",
        (exam_id, owner),
    ).fetchone()
    if existing:
        return {"id": existing["id"], "cert_no": existing["cert_no"], "already": True}

    issued_at = datetime.utcnow().isoformat(timespec="seconds")
    cert_no = _cert_no(exam_id, owner, issued_at)
    level = level_for(accuracy)
    connection.execute(
        """INSERT INTO certificates
        (cert_no, user_id, profile_id, exam_id, title, accuracy, score, pass_score, level, issued_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (cert_no, owner, profile_id, exam_id, title, round(accuracy, 1), round(score, 1),
         pass_score, level, issued_at),
    )
    return {"id": connection.execute("SELECT last_insert_rowid()").fetchone()[0],
            "cert_no": cert_no, "already": False, "level": level, "accuracy": round(accuracy, 1)}