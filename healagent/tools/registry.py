"""Tool registry and substitution map."""

from __future__ import annotations

from collections.abc import Mapping

from healagent.core.interfaces import Tool
from healagent.data.generator import EcommerceWorld, default_world

from .base import SchemaTool
from .ecommerce import (
    CalculatorTool,
    CustomerLookupTool,
    EvidenceCheckerTool,
    InventoryLookupTool,
    OrderLookupBackupTool,
    OrderLookupTool,
    PolicyLookupTool,
    RefundCalculatorTool,
    ShippingEstimatorBackupTool,
    ShippingEstimatorTool,
)

SUBSTITUTES: dict[str, str] = {
    "shipping_estimator": "shipping_estimator_backup",
    "calculator": "refund_calculator",
    "order_lookup": "order_lookup_backup",
}

TOOL_CLASSES: tuple[type[SchemaTool], ...] = (
    CustomerLookupTool,
    OrderLookupTool,
    InventoryLookupTool,
    ShippingEstimatorTool,
    PolicyLookupTool,
    CalculatorTool,
    EvidenceCheckerTool,
    ShippingEstimatorBackupTool,
    RefundCalculatorTool,
    OrderLookupBackupTool,
)

TOOLS: dict[str, Tool] = {}


def build_registry(world: EcommerceWorld | None = None) -> dict[str, Tool]:
    selected_world = world or default_world()
    return {tool.name: tool for tool in (tool_cls(selected_world) for tool_cls in TOOL_CLASSES)}


def default_registry() -> dict[str, Tool]:
    global TOOLS
    if not TOOLS:
        TOOLS = build_registry()
    return TOOLS


def get_tool(name: str, registry: Mapping[str, Tool] | None = None) -> Tool:
    tools = registry or default_registry()
    try:
        return tools[name]
    except KeyError as exc:
        raise KeyError(f"unknown tool: {name}") from exc


def list_schemas(registry: Mapping[str, Tool] | None = None) -> dict[str, dict]:
    tools = registry or default_registry()
    schemas: dict[str, dict] = {}
    for name, tool in tools.items():
        if isinstance(tool, SchemaTool):
            schemas[name] = tool.input_model.model_json_schema()
    return schemas
