from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import (
    _organization_slug,
    ensure_local_organization,
    get_db,
    record_audit_log,
)
from ..org_deps import get_membership
from . import auth as auth_module
from .auth import get_current_user


router = APIRouter(prefix="/organizations", tags=["organizations"])


def _require_authenticated(user: dict | None) -> None:
    if user is None and auth_module.AUTH_ENABLED:
        raise HTTPException(status_code=401, detail="请先登录")


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=80)


def _organization_payload(row: sqlite3.Row, *, role: str | None = None) -> dict:
    result = {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "status": row["status"],
        "owner_user_id": row["owner_user_id"],
        "settings": row["settings"],
        "created_at": row["created_at"],
    }
    if role is not None:
        result["role"] = role
    return result


@router.get("")
def list_organizations(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(get_current_user),
) -> list[dict]:
    _require_authenticated(user)
    if user is None:
        rows = connection.execute(
            "SELECT * FROM organizations WHERE status = 'active' ORDER BY created_at, id"
        ).fetchall()
        return [
            {**_organization_payload(row, role="owner"), "is_active": row["slug"] == "local"}
            for row in rows
        ]

    rows = connection.execute(
        """
        SELECT o.*, om.role, u.active_organization_id
        FROM organization_members AS om
        JOIN organizations AS o ON o.id = om.organization_id
        JOIN users AS u ON u.id = om.user_id
        WHERE om.user_id = ? AND om.status = 'active' AND o.status = 'active'
        ORDER BY o.created_at, o.id
        """,
        (int(user["id"]),),
    ).fetchall()
    return [
        {
            **_organization_payload(row, role=row["role"]),
            "is_active": int(row["id"]) == int(row["active_organization_id"] or 0),
        }
        for row in rows
    ]


@router.post("", status_code=201)
def create_organization(
    request: OrganizationCreate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(get_current_user),
) -> dict:
    _require_authenticated(user)
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="组织名称不能为空")
    owner_user_id = int(user["id"]) if user else None
    slug = _organization_slug(connection, request.slug or name)
    try:
        cursor = connection.execute(
            """
            INSERT INTO organizations(name, slug, owner_user_id, settings)
            VALUES (?, ?, ?, '{}')
            """,
            (name, slug, owner_user_id),
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="组织标识已存在") from error
    organization_id = int(cursor.lastrowid)
    if owner_user_id is not None:
        connection.execute(
            """
            INSERT INTO organization_members(organization_id, user_id, role, status)
            VALUES (?, ?, 'owner', 'active')
            """,
            (organization_id, owner_user_id),
        )
        connection.execute(
            "UPDATE users SET active_organization_id = ? WHERE id = ?",
            (organization_id, owner_user_id),
        )
    record_audit_log(
        connection,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        action="organization.created",
        resource_type="organization",
        resource_id=organization_id,
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM organizations WHERE id = ?", (organization_id,)
    ).fetchone()
    return _organization_payload(row, role="owner")


@router.get("/{organization_id}")
def get_organization(
    organization_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(get_current_user),
) -> dict:
    _require_authenticated(user)
    row = connection.execute(
        "SELECT * FROM organizations WHERE id = ? AND status = 'active'",
        (organization_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    role = "owner"
    if user is not None:
        membership = get_membership(connection, int(user["id"]), organization_id)
        if membership is None:
            raise HTTPException(status_code=403, detail="不是该组织成员")
        role = str(membership["role"])
    members = connection.execute(
        """
        SELECT u.id AS user_id, u.username, om.role, om.status, om.joined_at
        FROM organization_members AS om
        JOIN users AS u ON u.id = om.user_id
        WHERE om.organization_id = ? AND om.status = 'active'
        ORDER BY om.joined_at, u.id
        """,
        (organization_id,),
    ).fetchall()
    return {
        **_organization_payload(row, role=role),
        "members": [dict(member) for member in members],
    }


@router.post("/{organization_id}/switch")
def switch_organization(
    organization_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(get_current_user),
) -> dict:
    _require_authenticated(user)
    if user is None:
        row = connection.execute(
            "SELECT id FROM organizations WHERE id = ? AND status = 'active'",
            (organization_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="组织不存在")
        return {"switched": True, "organization_id": organization_id}
    membership = get_membership(connection, int(user["id"]), organization_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="不是该组织成员")
    connection.execute(
        "UPDATE users SET active_organization_id = ? WHERE id = ?",
        (organization_id, int(user["id"])),
    )
    record_audit_log(
        connection,
        organization_id=organization_id,
        actor_user_id=int(user["id"]),
        action="organization.switched",
        resource_type="organization",
        resource_id=organization_id,
    )
    connection.commit()
    return {"switched": True, "organization_id": organization_id}
