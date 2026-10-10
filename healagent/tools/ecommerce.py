"""Deterministic simulated e-commerce tools."""

from __future__ import annotations

import ast
import operator
from typing import Any, Callable

from pydantic import BaseModel, Field

from healagent.data.generator import Order, PolicyTable, SKU

from .base import SchemaTool


class CustomerLookupInput(BaseModel):
    customer_id: str = Field(pattern=r"^C\d{3}$")


class OrderLookupInput(BaseModel):
    order_id: str = Field(pattern=r"^O\d{3}$")


class InventoryLookupInput(BaseModel):
    sku: str = Field(pattern=r"^SKU\d{3}$")


class ShippingEstimatorInput(BaseModel):
    zip: str = Field(pattern=r"^\d{5}$")
    weight: float = Field(gt=0)


class PolicyLookupInput(BaseModel):
    topic: str = Field(min_length=1)


class CalculatorInput(BaseModel):
    expression: str = Field(min_length=1, max_length=120)


class EvidenceSource(BaseModel):
    source: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class EvidenceCheckerInput(BaseModel):
    claim: str = Field(min_length=1)
    sources: list[EvidenceSource] = Field(min_length=1)


class CustomerLookupTool(SchemaTool[CustomerLookupInput]):
    name = "customer_lookup"
    input_model = CustomerLookupInput
    latency_ms = 12.0

    def run(self, args: CustomerLookupInput) -> dict:
        customer = self.world.customers[args.customer_id]
        return customer.model_dump(mode="json")


class OrderLookupTool(SchemaTool[OrderLookupInput]):
    name = "order_lookup"
    input_model = OrderLookupInput
    latency_ms = 16.0

    def run(self, args: OrderLookupInput) -> dict:
        return _order_payload(self.world.orders[args.order_id])


class OrderLookupBackupTool(SchemaTool[OrderLookupInput]):
    name = "order_lookup_backup"
    input_model = OrderLookupInput
    latency_ms = 24.0

    def run(self, args: OrderLookupInput) -> dict:
        payload = _order_payload(self.world.orders[args.order_id])
        payload["source"] = "replica"
        return payload


class InventoryLookupTool(SchemaTool[InventoryLookupInput]):
    name = "inventory_lookup"
    input_model = InventoryLookupInput
    latency_ms = 10.0

    def run(self, args: InventoryLookupInput) -> dict:
        sku = self.world.skus[args.sku]
        return _sku_payload(sku)


class ShippingEstimatorTool(SchemaTool[ShippingEstimatorInput]):
    name = "shipping_estimator"
    input_model = ShippingEstimatorInput
    latency_ms = 18.0

    def run(self, args: ShippingEstimatorInput) -> dict:
        return estimate_shipping(args.zip, args.weight, self.world.policy)


class ShippingEstimatorBackupTool(SchemaTool[ShippingEstimatorInput]):
    name = "shipping_estimator_backup"
    input_model = ShippingEstimatorInput
    latency_ms = 28.0

    def run(self, args: ShippingEstimatorInput) -> dict:
        estimate = estimate_shipping(args.zip, args.weight, self.world.policy)
        estimate["source"] = "regional_backup"
        return estimate


class PolicyLookupTool(SchemaTool[PolicyLookupInput]):
    name = "policy_lookup"
    input_model = PolicyLookupInput
    latency_ms = 8.0

    def run(self, args: PolicyLookupInput) -> dict:
        topic = args.topic.strip().lower()
        if topic not in self.world.policy.topics:
            raise KeyError(topic)
        return {
            "topic": topic,
            "policy": self.world.policy.topics[topic],
            "as_of": self.world.policy.today.isoformat(),
        }


class CalculatorTool(SchemaTool[CalculatorInput]):
    name = "calculator"
    input_model = CalculatorInput
    latency_ms = 6.0

    def run(self, args: CalculatorInput) -> dict:
        return _calculator_payload(args.expression)


class RefundCalculatorTool(SchemaTool[CalculatorInput]):
    name = "refund_calculator"
    input_model = CalculatorInput
    latency_ms = 9.0

    def run(self, args: CalculatorInput) -> dict:
        payload = _calculator_payload(args.expression)
        payload["source"] = "refund_calculator"
        return payload


class EvidenceCheckerTool(SchemaTool[EvidenceCheckerInput]):
    name = "evidence_checker"
    input_model = EvidenceCheckerInput
    latency_ms = 14.0

    def run(self, args: EvidenceCheckerInput) -> dict:
        sources = sorted(
            args.sources,
            key=lambda source: (-source.confidence, source.source, source.value),
        )
        best = sources[0]
        values = sorted({source.value for source in sources})
        claim_norm = _normalise(args.claim)
        supported = _normalise(best.value) in claim_norm
        return {
            "claim": args.claim,
            "supported": supported,
            "resolved_value": best.value,
            "best_source": best.source,
            "confidence": best.confidence,
            "conflicts": values if len(values) > 1 else [],
        }


def estimate_shipping(zip_code: str, weight: float, policy: PolicyTable) -> dict:
    zone = zip_code[0]
    zone_days = policy.standard_days_by_zone.get(zone, 5)
    zone_factor = 1.0 + abs(int(zone) - 5) * 0.06
    cost = policy.base_shipping + policy.per_lb_shipping * weight * zone_factor
    return {
        "zip": zip_code,
        "weight": round(weight, 2),
        "service": "ground",
        "estimated_days": zone_days,
        "shipping_cost": round(cost, 2),
    }


def _order_payload(order: Order) -> dict:
    payload = order.model_dump(mode="json")
    payload["item_count"] = sum(item.quantity for item in order.items)
    payload["source"] = "primary"
    return payload


def _sku_payload(sku: SKU) -> dict:
    payload = sku.model_dump(mode="json")
    payload["available"] = sku.stock > 0
    return payload


def _calculator_payload(expression: str) -> dict:
    value = _safe_eval(expression)
    return {
        "expression": expression,
        "result": round(float(value), 2),
    }


ALLOWED_OPERATORS: dict[type[ast.operator | ast.unaryop], Callable[..., float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(expression: str) -> float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("expression must be arithmetic") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op = ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("unsupported arithmetic operator")
        return float(op(_eval_node(node.left), _eval_node(node.right)))
    if isinstance(node, ast.UnaryOp):
        op = ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("unsupported arithmetic operator")
        return float(op(_eval_node(node.operand)))
    raise ValueError("expression must contain only numbers and arithmetic operators")


def _normalise(value: Any) -> str:
    return str(value).strip().lower()
