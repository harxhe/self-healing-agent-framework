"""Scripted answer synthesis for no-LLM task execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from healagent.core.types import Task

ToolOutputs = Mapping[str, Sequence[Mapping[str, Any]]]


def synthesize_answer(task: Task, outputs: ToolOutputs) -> dict[str, Any]:
    if task.category == "order_status":
        return _order_status(outputs)
    if task.category == "refund_eligibility":
        return _refund_eligibility(outputs)
    if task.category == "stock_and_shipping":
        return _stock_and_shipping(task, outputs)
    if task.category == "multi_step_workflow":
        return _multi_step_workflow(outputs)
    if task.category == "contradiction_resolution":
        return _contradiction_resolution(outputs)
    raise ValueError(f"unknown task category: {task.category}")


def _one(outputs: ToolOutputs, tool: str) -> Mapping[str, Any]:
    values = outputs.get(tool)
    if not values:
        raise ValueError(f"missing output for tool: {tool}")
    return values[0]


def _order_status(outputs: ToolOutputs) -> dict[str, Any]:
    order = _one(outputs, "order_lookup")
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "tracking_number": order["tracking_number"],
        "eta_date": order["eta_date"],
        "delivered_date": order["delivered_date"],
    }


def _refund_eligibility(outputs: ToolOutputs) -> dict[str, Any]:
    order = _one(outputs, "order_lookup")
    policy_result = _one(outputs, "policy_lookup")
    calculation = _one(outputs, "calculator")
    policy = policy_result["policy"]

    delivered_date = _parse_date(order["delivered_date"])
    today = date.fromisoformat(policy_result["as_of"])
    days_since_delivery = None
    if delivered_date is not None:
        days_since_delivery = (today - delivered_date).days

    eligible_status = order["status"] in policy["eligible_statuses"]
    eligible_window = (
        days_since_delivery is not None
        and days_since_delivery <= policy["refund_window_days"]
    )
    eligible = eligible_status and eligible_window

    if eligible:
        reason = "within_refund_window"
    elif not eligible_status:
        reason = f"status_{order['status']}"
    elif days_since_delivery is None:
        reason = "not_delivered"
    else:
        reason = "outside_refund_window"

    restocking_fee = round(order["subtotal"] * policy["restocking_fee_rate"], 2) if eligible else 0.0
    refund_amount = calculation["result"] if eligible else 0.0
    return {
        "order_id": order["order_id"],
        "eligible": eligible,
        "days_since_delivery": days_since_delivery,
        "restocking_fee": restocking_fee,
        "refund_amount": refund_amount,
        "reason": reason,
    }


def _stock_and_shipping(task: Task, outputs: ToolOutputs) -> dict[str, Any]:
    inventory = _one(outputs, "inventory_lookup")
    shipping = _one(outputs, "shipping_estimator")
    requested_quantity = int(task.success_criteria.get("requested_quantity", 1))
    return {
        "sku": inventory["sku"],
        "requested_quantity": requested_quantity,
        "available": inventory["stock"] >= requested_quantity,
        "stock": inventory["stock"],
        "estimated_days": shipping["estimated_days"],
        "shipping_cost": shipping["shipping_cost"],
    }


def _multi_step_workflow(outputs: ToolOutputs) -> dict[str, Any]:
    customer = _one(outputs, "customer_lookup")
    order = _one(outputs, "order_lookup")
    inventory = _one(outputs, "inventory_lookup")
    shipping = _one(outputs, "shipping_estimator")
    policy = _one(outputs, "policy_lookup")
    first_item = order["items"][0]
    quantity = first_item["quantity"]
    return {
        "customer_id": customer["customer_id"],
        "contact_email": customer["email"],
        "order_id": order["order_id"],
        "order_status": order["status"],
        "sku": inventory["sku"],
        "replacement_quantity": quantity,
        "replacement_available": inventory["stock"] >= quantity,
        "shipping_cost": shipping["shipping_cost"],
        "estimated_days": shipping["estimated_days"],
        "policy_topic": policy["topic"],
    }


def _contradiction_resolution(outputs: ToolOutputs) -> dict[str, Any]:
    evidence = _one(outputs, "evidence_checker")
    return {
        "claim_supported": evidence["supported"],
        "resolved_value": evidence["resolved_value"],
        "best_source": evidence["best_source"],
        "conflicts": evidence["conflicts"],
    }


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))
