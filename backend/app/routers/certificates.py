"""证书 & 防作弊 — 企业版两大功能接口。

- 证书：查看我的证书 / 证书详情 / 证书校验
- 防作弊：记录考试期间的切屏/剪切/无操作等异常事件
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from .auth import maybe_require_user

router = APIRouter(tags=["certificates"])


# ---------- 证书 ----------

@router.get("/api/certificates")
def my_certificates(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> list[dict]:
    """当前用户的全部证书（按颁发时间倒序）。"""
    where, params = ("WHERE user_id = ?", [user["id"]]) if user else ("", [])
    rows = connection.execute(
        f"""SELECT c.*, p.name AS profile_name
            FROM certificates c
            LEFT JOIN question_bank_profiles p ON p.id = c.profile_id
            {where}
            ORDER BY c.id DESC LIMIT 50""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/certificates/{cert_no}")
def certificate_detail(
    cert_no: str,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """按证书编号查询（对外校验用，无需登录）。"""
    row = connection.execute(
        """SELECT c.*, p.name AS profile_name
           FROM certificates c
           LEFT JOIN question_bank_profiles p ON p.id = c.profile_id
           WHERE c.cert_no = ?""",
        (cert_no,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "证书不存在")
    return dict(row)


@router.get("/api/certificates/verify/{cert_no}")
def verify_certificate(
    cert_no: str,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """证书真伪校验：返回证书信息 + 是否有效。"""
    row = connection.execute(
        "SELECT cert_no, title, level, accuracy, issued_at FROM certificates WHERE cert_no = ?",
        (cert_no,),
    ).fetchone()
    if row is None:
        return {"valid": False, "reason": "证书编号不存在"}
    return {"valid": True, "certificate": dict(row)}


# ---------- 防作弊 ----------

class AntiCheatEvent(BaseModel):
    event_type: str = Field(..., description="screen_switch / suspend / copy / paste / window_blur / inactivity")
    detail: str = ""


@router.post("/api/exams/{exam_id}/anti-cheat")
def record_anti_cheat(
    exam_id: int,
    request: AntiCheatEvent,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """记录一次防作弊事件。服务端只记录，不中断——由前端按策略处理。"""
    allowed = {"screen_switch", "suspend", "copy", "paste", "window_blur", "inactivity"}
    if request.event_type not in allowed:
        raise HTTPException(400, "未知的防作弊事件类型")
    exam = connection.execute(
        "SELECT id FROM exam_sessions WHERE id = ?", (exam_id,)
    ).fetchone()
    if exam is None:
        raise HTTPException(404, "考试不存在")
    connection.execute(
        """INSERT INTO anti_cheat_logs (exam_id, event_type, detail, user_id)
        VALUES (?, ?, ?, ?)""",
        (exam_id, request.event_type, request.detail[:500], user["id"] if user else None),
    )
    connection.commit()
    # 返回当前累计违规次数，方便前端决定是否强制交卷
    count = connection.execute(
        "SELECT COUNT(*) AS n FROM anti_cheat_logs WHERE exam_id = ?", (exam_id,)
    ).fetchone()["n"]
    return {"recorded": True, "event_type": request.event_type, "total_events": count}


@router.get("/api/exams/{exam_id}/anti-cheat")
def anti_cheat_log(
    exam_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """考试防作弊事件记录（管理端查看）。"""
    rows = connection.execute(
        """SELECT event_type, detail, occurred_at
           FROM anti_cheat_logs WHERE exam_id = ?
           ORDER BY id DESC""",
        (exam_id,),
    ).fetchall()
    return {"exam_id": exam_id, "events": [dict(r) for r in rows],
            "total": len(rows),
            "suspicious": sum(1 for r in rows if r["event_type"] in ("screen_switch", "window_blur"))}