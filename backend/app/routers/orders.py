"""P1 商业订单 API（当前阶段只支持人工收款确认）。"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from ..database import get_db
from ..org_deps import get_current_organization, get_membership
from ..schemas import OrderCreate
from ..services import order_service
from . import auth as auth_module
from .auth import maybe_require_user


router = APIRouter(prefix="/orders", tags=["orders"])


def _raise_order_error(error: order_service.OrderError) -> None:
    if isinstance(error, order_service.OrderNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, order_service.PlanNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, order_service.InvalidOrderStateError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


def _order_events(
    connection: sqlite3.Connection, order_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, order_id, event_type, amount_cents, meta_json, created_at
        FROM payment_events WHERE order_id = ? ORDER BY id
        """,
        (order_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["id"] = int(item["id"])
        item["order_id"] = int(item["order_id"])
        item["amount_cents"] = int(item["amount_cents"])
        result.append(item)
    return result


def _with_events(
    connection: sqlite3.Connection, order: dict[str, Any]
) -> dict[str, Any]:
    order["payment_events"] = _order_events(connection, int(order["id"]))
    return order


@router.post("", status_code=201)
def create_order(
    request: OrderCreate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
    organization: dict = Depends(get_current_organization),
) -> dict[str, Any]:
    """Create a pending order for the caller's active organization."""
    organization_id = int(organization["id"])
    if request.organization_id is not None and int(request.organization_id) != organization_id:
        # In authenticated mode the active organization dependency is the
        # authority.  Local mode has no user context, so it may explicitly
        # select one of the local organizations for compatibility.
        if auth_module.AUTH_ENABLED:
            raise HTTPException(status_code=403, detail="订单组织必须是当前组织")
        candidate = connection.execute(
            "SELECT id FROM organizations WHERE id = ? AND status = 'active'",
            (int(request.organization_id),),
        ).fetchone()
        if candidate is None:
            raise HTTPException(status_code=404, detail="组织不存在或已停用")
        organization_id = int(request.organization_id)
    try:
        order = order_service.create_order(
            connection,
            organization_id=organization_id,
            buyer_user_id=int(user["id"]) if user else None,
            plan_id=request.plan_id,
            amount_cents=request.amount_cents,
        )
    except order_service.OrderError as error:
        _raise_order_error(error)
    return _with_events(connection, order)


def _authorize_mark_paid(
    connection: sqlite3.Connection,
    order_id: int,
    user: dict | None,
) -> None:
    """Allow local mode, global admins, or owner/admin members of the org."""
    if user is None:
        if auth_module.AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="未登录")
        return
    if bool(user.get("is_admin")):
        return
    row = connection.execute(
        "SELECT organization_id FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    membership = get_membership(connection, int(user["id"]), int(row["organization_id"]))
    if membership is None or str(membership["role"]).lower() not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="需要组织 owner/admin 权限")


@router.post("/{order_id}/mark-paid")
def mark_order_paid(
    order_id: int = Path(gt=0),
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    """Record manual collection; this endpoint never calls a payment gateway."""
    _authorize_mark_paid(connection, order_id, user)
    try:
        order = order_service.mark_paid(
            connection,
            order_id,
            actor_user_id=int(user["id"]) if user else None,
        )
    except order_service.OrderError as error:
        _raise_order_error(error)
    return _with_events(connection, order)


@router.get("/{order_id}")
def get_order(
    order_id: int = Path(gt=0),
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
    organization: dict = Depends(get_current_organization),
) -> dict[str, Any]:
    """Return an order only within the caller's active organization."""
    try:
        order = order_service.get_order(connection, order_id)
    except order_service.OrderError as error:
        _raise_order_error(error)
    if int(order["organization_id"]) != int(organization["id"]):
        raise HTTPException(status_code=404, detail="订单不存在")
    return _with_events(connection, order)
