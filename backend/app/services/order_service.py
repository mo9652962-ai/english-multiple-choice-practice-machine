"""商业订单服务：订单创建、人工收款和严格状态机。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator
from uuid import uuid4


ORDER_STATUSES = frozenset(
    {"pending", "paid", "cancelled", "refunding", "refunded", "failed"}
)
_ALLOWED_TRANSITIONS = {
    "pending": frozenset({"paid", "cancelled", "failed"}),
    "paid": frozenset({"refunding"}),
    "refunding": frozenset({"refunded"}),
    "cancelled": frozenset(),
    "failed": frozenset(),
    "refunded": frozenset(),
}


class OrderError(ValueError):
    """Base class for expected order-domain errors."""


class OrderNotFoundError(OrderError):
    pass


class PlanNotFoundError(OrderError):
    pass


class OrderValidationError(OrderError):
    pass


class InvalidOrderStateError(OrderError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _validate_positive_id(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OrderValidationError(f"{field} 必须是正整数")
    return value


def _validate_cents(value: int, field: str = "amount_cents") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrderValidationError(f"{field} 必须是非负整数分")
    return value


def _json_text(value: dict[str, Any] | None) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise OrderValidationError("meta 必须是可序列化的 JSON 对象") from error


def _decode_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


@contextmanager
def _write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    """Serialize a mutation without swallowing a caller's transaction."""
    savepoint = f"order_write_{uuid4().hex}"
    owns_transaction = not connection.in_transaction
    if owns_transaction:
        connection.execute("BEGIN IMMEDIATE")
    else:
        connection.execute(f"SAVEPOINT {savepoint}")
    try:
        yield
    except Exception:
        if owns_transaction:
            connection.rollback()
        else:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
    else:
        if owns_transaction:
            connection.commit()
        else:
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")


def _new_order_no(connection: sqlite3.Connection) -> str:
    for _ in range(5):
        candidate = f"ORD-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:12].upper()}"
        if not connection.execute(
            "SELECT 1 FROM orders WHERE order_no = ?", (candidate,)
        ).fetchone():
            return candidate
    raise OrderValidationError("无法生成唯一订单号")


def _row_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["id"] = int(payload["id"])
    payload["organization_id"] = int(payload["organization_id"])
    payload["plan_id"] = int(payload["plan_id"])
    if payload.get("buyer_user_id") is not None:
        payload["buyer_user_id"] = int(payload["buyer_user_id"])
    payload["amount_cents"] = int(payload["amount_cents"])
    payload["plan"] = {
        "id": payload["plan_id"],
        "name": payload.pop("plan_name"),
        "duration_days": int(payload.pop("plan_duration_days")),
        "features": _decode_json(payload.pop("plan_features_json"), []),
    }
    return payload


def _fetch_order(connection: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT o.*, p.name AS plan_name, p.duration_days AS plan_duration_days,
               p.features_json AS plan_features_json
        FROM orders AS o
        JOIN plans AS p ON p.id = o.plan_id
        WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()
    if row is None:
        raise OrderNotFoundError("订单不存在")
    return row


def get_order(connection: sqlite3.Connection, order_id: int) -> dict[str, Any]:
    """Return one order without exposing a mutable sqlite Row."""
    _validate_positive_id(order_id, "order_id")
    return _row_payload(_fetch_order(connection, order_id))


def _transition(
    connection: sqlite3.Connection,
    order_id: int,
    target_status: str,
    *,
    paid_at: str | None = None,
    expires_at: str | None = None,
    event_type: str | None = None,
    event_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_positive_id(order_id, "order_id")
    if target_status not in ORDER_STATUSES:
        raise OrderValidationError("未知订单状态")
    with _write_transaction(connection):
        row = _fetch_order(connection, order_id)
        current = str(row["status"])
        if target_status not in _ALLOWED_TRANSITIONS[current]:
            raise InvalidOrderStateError(
                f"订单状态不能从 {current} 变更为 {target_status}"
            )
        now = _now()
        connection.execute(
            """
            UPDATE orders
            SET status = ?, paid_at = COALESCE(?, paid_at),
                expires_at = COALESCE(?, expires_at), updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (target_status, paid_at, expires_at, now, order_id, current),
        )
        if connection.execute("SELECT changes()").fetchone()[0] != 1:
            raise InvalidOrderStateError("订单状态已被其他请求修改，请重试")
        if event_type is not None:
            connection.execute(
                """
                INSERT INTO payment_events(order_id, event_type, amount_cents, meta_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    event_type,
                    int(row["amount_cents"]),
                    _json_text(event_meta),
                ),
            )
        return get_order(connection, order_id)


def create_order(
    connection: sqlite3.Connection,
    organization_id: int,
    buyer_user_id: int | None,
    plan_id: int,
    amount_cents: int,
) -> dict[str, Any]:
    """Create a pending order; the amount must match the active plan exactly."""
    _validate_positive_id(organization_id, "organization_id")
    _validate_positive_id(plan_id, "plan_id")
    if buyer_user_id is not None:
        _validate_positive_id(buyer_user_id, "buyer_user_id")
    amount_cents = _validate_cents(amount_cents)
    with _write_transaction(connection):
        plan = connection.execute(
            """
            SELECT id, price_cents, duration_days
            FROM plans WHERE id = ? AND active = 1
            """,
            (plan_id,),
        ).fetchone()
        if plan is None:
            raise PlanNotFoundError("商品计划不存在或未启用")
        if not isinstance(plan["price_cents"], int) or amount_cents != int(
            plan["price_cents"]
        ):
            raise OrderValidationError("订单金额必须与计划价格一致，且使用整数分")
        if not connection.execute(
            "SELECT 1 FROM organizations WHERE id = ? AND status = 'active'",
            (organization_id,),
        ).fetchone():
            raise OrderValidationError("组织不存在或已停用")
        order_no = _new_order_no(connection)
        cursor = connection.execute(
            """
            INSERT INTO orders
                (order_no, organization_id, buyer_user_id, plan_id, amount_cents)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_no, organization_id, buyer_user_id, plan_id, amount_cents),
        )
        return get_order(connection, int(cursor.lastrowid))


def mark_paid(
    connection: sqlite3.Connection,
    order_id: int,
    *,
    actor_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark a pending order paid for an offline/manual collection.

    A second call for an already-paid order is deliberately idempotent: it
    returns the existing order and does not append another payment event.
    """
    _validate_positive_id(order_id, "order_id")
    if actor_user_id is not None:
        _validate_positive_id(actor_user_id, "actor_user_id")
    amount_meta = dict(meta or {})
    amount_meta.setdefault("channel", "manual")
    if actor_user_id is not None:
        amount_meta.setdefault("actor_user_id", actor_user_id)
    with _write_transaction(connection):
        row = _fetch_order(connection, order_id)
        if row["status"] == "paid":
            return get_order(connection, order_id)
        if row["status"] != "pending":
            raise InvalidOrderStateError(
                f"订单状态不能从 {row['status']} 变更为 paid"
            )
        paid_at = _now()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=int(row["plan_duration_days"]))
        ).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        connection.execute(
            """
            UPDATE orders
            SET status = 'paid', paid_at = ?, expires_at = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (paid_at, expires_at, paid_at, order_id),
        )
        if connection.execute("SELECT changes()").fetchone()[0] != 1:
            raise InvalidOrderStateError("订单状态已被其他请求修改，请重试")
        connection.execute(
            """
            INSERT INTO payment_events(order_id, event_type, amount_cents, meta_json)
            VALUES (?, 'manual_paid', ?, ?)
            """,
            (order_id, int(row["amount_cents"]), _json_text(amount_meta)),
        )
        return get_order(connection, order_id)


def cancel(connection: sqlite3.Connection, order_id: int) -> dict[str, Any]:
    return _transition(connection, order_id, "cancelled")


def fail(connection: sqlite3.Connection, order_id: int) -> dict[str, Any]:
    return _transition(connection, order_id, "failed")


def refund(
    connection: sqlite3.Connection,
    order_id: int,
    *,
    actor_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Request a refund; no external payment/refund is performed here."""
    if actor_user_id is not None:
        _validate_positive_id(actor_user_id, "actor_user_id")
    event_meta = dict(meta or {})
    event_meta.setdefault("actor_user_id", actor_user_id)
    return _transition(
        connection,
        order_id,
        "refunding",
        event_type="refund_requested",
        event_meta=event_meta,
    )


def mark_refunded(
    connection: sqlite3.Connection,
    order_id: int,
    *,
    actor_user_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Complete the state transition after a refund is confirmed manually."""
    if actor_user_id is not None:
        _validate_positive_id(actor_user_id, "actor_user_id")
    event_meta = dict(meta or {})
    event_meta.setdefault("actor_user_id", actor_user_id)
    return _transition(
        connection,
        order_id,
        "refunded",
        event_type="refunded",
        event_meta=event_meta,
    )


request_refund = refund
complete_refund = mark_refunded
