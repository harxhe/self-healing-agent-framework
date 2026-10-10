"""Build and load the deterministic Phase 1 task catalog."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from healagent.core.types import FailureClass, PlanStep, Task
from healagent.data.generator import EcommerceWorld, Order, default_world
from healagent.tools.registry import build_registry

from .executor import run_task

TASKS_PATH = Path(__file__).with_name("tasks.json")
TASKS_PER_CATEGORY = 20


def load_tasks(path: Path | str = TASKS_PATH) -> list[Task]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Task.model_validate(item) for item in data]


def build_tasks(world: EcommerceWorld | None = None) -> list[Task]:
    selected_world = world or default_world()
    tasks = [
        *_order_status_tasks(selected_world),
        *_refund_eligibility_tasks(selected_world),
        *_stock_and_shipping_tasks(selected_world),
        *_multi_step_workflow_tasks(selected_world),
        *_contradiction_resolution_tasks(selected_world),
    ]
    return _with_expected_answers(tasks, selected_world)


def write_tasks_json(path: Path | str = TASKS_PATH) -> None:
    tasks = build_tasks()
    payload = [task.model_dump(mode="json") for task in tasks]
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _with_expected_answers(tasks: list[Task], world: EcommerceWorld) -> list[Task]:
    registry = build_registry(world)
    completed: list[Task] = []
    for task in tasks:
        result = run_task(task, registry)
        if not result.ok:
            raise ValueError(f"{task.task_id} did not execute cleanly: {result.errors}")
        completed.append(task.model_copy(update={"expected_answer": result.final_answer}))

    counts = Counter(task.category for task in completed)
    if set(counts.values()) != {TASKS_PER_CATEGORY}:
        raise ValueError(f"expected {TASKS_PER_CATEGORY} tasks per category, got {counts}")
    return completed


def _order_status_tasks(world: EcommerceWorld) -> list[Task]:
    tasks: list[Task] = []
    for idx, order_id in enumerate(_order_ids(0, TASKS_PER_CATEGORY), start=1):
        tasks.append(
            Task(
                task_id=f"T{idx:03d}",
                category="order_status",
                request=f"Tell the customer the current status and tracking details for order {order_id}.",
                plan=[PlanStep(tool="order_lookup", args={"order_id": order_id})],
                success_criteria={"type": "exact_match"},
                eligible_faults=_faults(
                    FailureClass.TIMEOUT,
                    FailureClass.UNAVAILABLE,
                    FailureClass.RATE_LIMIT,
                    FailureClass.PARTIAL_RESPONSE,
                    FailureClass.STALE_CONTEXT,
                ),
            )
        )
    return tasks


def _refund_eligibility_tasks(world: EcommerceWorld) -> list[Task]:
    tasks: list[Task] = []
    for offset, order_id in enumerate(_order_ids(20, TASKS_PER_CATEGORY), start=21):
        order = world.orders[order_id]
        expression = _refund_expression(order, world)
        tasks.append(
            Task(
                task_id=f"T{offset:03d}",
                category="refund_eligibility",
                request=f"Check whether order {order_id} is eligible for a refund and compute the amount.",
                plan=[
                    PlanStep(tool="order_lookup", args={"order_id": order_id}),
                    PlanStep(tool="policy_lookup", args={"topic": "refund"}),
                    PlanStep(tool="calculator", args={"expression": expression}),
                ],
                success_criteria={"type": "exact_match"},
                eligible_faults=_faults(
                    FailureClass.TIMEOUT,
                    FailureClass.PARTIAL_RESPONSE,
                    FailureClass.SCHEMA_ERROR,
                    FailureClass.SEMANTIC_WRONG,
                ),
            )
        )
    return tasks


def _stock_and_shipping_tasks(world: EcommerceWorld) -> list[Task]:
    tasks: list[Task] = []
    sku_ids = list(world.skus)
    customer_ids = list(world.customers)
    for offset in range(TASKS_PER_CATEGORY):
        sku = world.skus[sku_ids[offset]]
        customer = world.customers[customer_ids[(offset * 3) % len(customer_ids)]]
        quantity = 1 + offset % 5
        tasks.append(
            Task(
                task_id=f"T{offset + 41:03d}",
                category="stock_and_shipping",
                request=(
                    f"Can customer {customer.customer_id} buy {quantity} units of {sku.sku}, "
                    "and what would standard shipping cost?"
                ),
                plan=[
                    PlanStep(tool="inventory_lookup", args={"sku": sku.sku}),
                    PlanStep(
                        tool="shipping_estimator",
                        args={"zip": customer.zip, "weight": round(sku.weight * quantity, 2)},
                    ),
                ],
                success_criteria={"type": "exact_match", "requested_quantity": quantity},
                eligible_faults=_faults(
                    FailureClass.TIMEOUT,
                    FailureClass.PARTIAL_RESPONSE,
                    FailureClass.STALE_CONTEXT,
                    FailureClass.SEMANTIC_WRONG,
                ),
            )
        )
    return tasks


def _multi_step_workflow_tasks(world: EcommerceWorld) -> list[Task]:
    tasks: list[Task] = []
    for offset, order_id in enumerate(_order_ids(0, TASKS_PER_CATEGORY), start=61):
        order = world.orders[order_id]
        first_item = order.items[0]
        customer = world.customers[order.customer_id]
        tasks.append(
            Task(
                task_id=f"T{offset:03d}",
                category="multi_step_workflow",
                request=(
                    f"Prepare a replacement workflow for {customer.customer_id} on order {order_id}, "
                    f"starting with SKU {first_item.sku}."
                ),
                plan=[
                    PlanStep(tool="customer_lookup", args={"customer_id": customer.customer_id}),
                    PlanStep(tool="order_lookup", args={"order_id": order_id}),
                    PlanStep(tool="inventory_lookup", args={"sku": first_item.sku}),
                    PlanStep(
                        tool="shipping_estimator",
                        args={
                            "zip": order.shipping_zip,
                            "weight": round(first_item.weight * first_item.quantity, 2),
                        },
                    ),
                    PlanStep(tool="policy_lookup", args={"topic": "replacement"}),
                ],
                success_criteria={"type": "exact_match"},
                eligible_faults=_faults(
                    FailureClass.TIMEOUT,
                    FailureClass.UNAVAILABLE,
                    FailureClass.RATE_LIMIT,
                    FailureClass.STALE_CONTEXT,
                    FailureClass.MALFORMED_OUTPUT,
                    FailureClass.PARTIAL_RESPONSE,
                    FailureClass.SEMANTIC_WRONG,
                ),
            )
        )
    return tasks


def _contradiction_resolution_tasks(world: EcommerceWorld) -> list[Task]:
    tasks: list[Task] = []
    for offset, order_id in enumerate(_order_ids(30, TASKS_PER_CATEGORY), start=81):
        order = world.orders[order_id]
        conflicting_status = _alternate_status(order.status, offset)
        claim_status = conflicting_status if offset % 2 == 0 else order.status
        tasks.append(
            Task(
                task_id=f"T{offset:03d}",
                category="contradiction_resolution",
                request=f"Resolve conflicting evidence about the status of order {order_id}.",
                plan=[
                    PlanStep(
                        tool="evidence_checker",
                        args={
                            "claim": f"The order status is {claim_status}.",
                            "sources": [
                                {
                                    "source": "email_thread",
                                    "value": conflicting_status,
                                    "confidence": 0.45 + (offset % 3) * 0.05,
                                },
                                {
                                    "source": "order_system",
                                    "value": order.status,
                                    "confidence": 0.95,
                                },
                                {
                                    "source": "warehouse_note",
                                    "value": order.status if offset % 3 else conflicting_status,
                                    "confidence": 0.7,
                                },
                            ],
                        },
                    )
                ],
                success_criteria={"type": "exact_match"},
                eligible_faults=_faults(
                    FailureClass.CONTRADICTORY_EVIDENCE,
                    FailureClass.SEMANTIC_WRONG,
                    FailureClass.MALFORMED_OUTPUT,
                    FailureClass.PARTIAL_RESPONSE,
                ),
            )
        )
    return tasks


def _refund_expression(order: Order, world: EcommerceWorld) -> str:
    policy = world.policy
    delivered_date = order.delivered_date
    eligible_status = order.status in policy.topics["refund"]["eligible_statuses"]
    eligible_window = (
        delivered_date is not None
        and (policy.today - delivered_date).days <= policy.refund_window_days
    )
    if not (eligible_status and eligible_window):
        return "0"
    return f"{order.subtotal:.2f} * (1 - {policy.restocking_fee_rate:.2f})"


def _order_ids(start: int, count: int) -> list[str]:
    return [f"O{idx + 1:03d}" for idx in range(start, start + count)]


def _alternate_status(status: str, offset: int) -> str:
    options = ["processing", "shipped", "delivered", "returned", "cancelled"]
    return options[(options.index(status) + 1 + offset % (len(options) - 1)) % len(options)]


def _faults(*classes: FailureClass) -> list[str]:
    return [failure_class.value for failure_class in classes]


if __name__ == "__main__":
    write_tasks_json()
