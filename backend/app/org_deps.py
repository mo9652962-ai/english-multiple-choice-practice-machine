from __future__ import annotations

import sqlite3
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Query

from .database import ensure_local_organization, get_db
from .routers import auth as auth_module
from .routers.auth import get_current_user


def _organization_row(connection: sqlite3.Connection, organization_id: int):
    return connection.execute(
        """
        SELECT id, name, slug, status, owner_user_id, settings, created_at
        FROM organizations
        WHERE id = ? AND status = 'active'
        """,
        (organization_id,),
    ).fetchone()


def get_membership(
    connection: sqlite3.Connection,
    user_id: int,
    organization_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT om.organization_id, om.user_id, om.role, om.status, om.joined_at,
               o.id, o.name, o.slug, o.status AS organization_status,
               o.owner_user_id, o.settings, o.created_at
        FROM organization_members AS om
        JOIN organizations AS o ON o.id = om.organization_id
        WHERE om.organization_id = ? AND om.user_id = ?
          AND om.status = 'active' AND o.status = 'active'
        """,
        (organization_id, user_id),
    ).fetchone()


def get_current_organization(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(get_current_user),
    org_id: int | None = Query(default=None),
    x_organization_id: int | None = Header(default=None),
) -> dict:
    """Resolve the active organization and enforce membership when auth is on."""
    requested_id = x_organization_id if x_organization_id is not None else org_id
    if user is None:
        if auth_module.AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="请先登录")
        organization_id = requested_id or ensure_local_organization(connection)
        row = _organization_row(connection, organization_id)
        if row is None:
            raise HTTPException(status_code=404, detail="组织不存在")
        return {**dict(row), "role": "owner", "member_user_id": None}

    if requested_id is not None:
        membership = get_membership(connection, int(user["id"]), int(requested_id))
        if membership is None:
            raise HTTPException(status_code=403, detail="不是该组织成员")
        connection.execute(
            "UPDATE users SET active_organization_id = ? WHERE id = ?",
            (int(requested_id), int(user["id"])),
        )
        return {
            "id": membership["id"],
            "name": membership["name"],
            "slug": membership["slug"],
            "status": membership["organization_status"],
            "owner_user_id": membership["owner_user_id"],
            "settings": membership["settings"],
            "created_at": membership["created_at"],
            "role": membership["role"],
            "member_user_id": membership["user_id"],
        }

    active = connection.execute(
        """
        SELECT u.active_organization_id
        FROM users AS u WHERE u.id = ?
        """,
        (int(user["id"]),),
    ).fetchone()
    candidates: list[int] = []
    if active and active["active_organization_id"] is not None:
        candidates.append(int(active["active_organization_id"]))
    first = connection.execute(
        """
        SELECT organization_id FROM organization_members
        WHERE user_id = ? AND status = 'active'
        ORDER BY joined_at, organization_id LIMIT 1
        """,
        (int(user["id"]),),
    ).fetchone()
    if first:
        candidates.append(int(first["organization_id"]))
    for candidate in candidates:
        membership = get_membership(connection, int(user["id"]), candidate)
        if membership:
            if active is None or active["active_organization_id"] != candidate:
                connection.execute(
                    "UPDATE users SET active_organization_id = ? WHERE id = ?",
                    (candidate, int(user["id"])),
                )
            return {
                "id": membership["id"],
                "name": membership["name"],
                "slug": membership["slug"],
                "status": membership["organization_status"],
                "owner_user_id": membership["owner_user_id"],
                "settings": membership["settings"],
                "created_at": membership["created_at"],
                "role": membership["role"],
                "member_user_id": membership["user_id"],
            }
    raise HTTPException(status_code=403, detail="没有可用的组织")


def require_org_role(*roles: str) -> Callable:
    """Build a FastAPI dependency that checks the current org role."""
    allowed = {role.strip().lower() for role in roles if role.strip()}

    def dependency(
        organization: dict = Depends(get_current_organization),
    ) -> dict:
        role = str(organization.get("role") or "").lower()
        if allowed and role not in allowed:
            raise HTTPException(status_code=403, detail="组织角色权限不足")
        return organization

    return dependency
