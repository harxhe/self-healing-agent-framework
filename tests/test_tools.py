from __future__ import annotations

from healagent.data.generator import default_world
from healagent.tools.registry import SUBSTITUTES, build_registry, list_schemas


def test_registry_contains_primary_and_backup_tools() -> None:
    registry = build_registry()

    assert set(registry) == {
        "customer_lookup",
        "order_lookup",
        "inventory_lookup",
        "shipping_estimator",
        "policy_lookup",
        "calculator",
        "evidence_checker",
        "shipping_estimator_backup",
        "refund_calculator",
        "order_lookup_backup",
    }
    assert SUBSTITUTES == {
        "shipping_estimator": "shipping_estimator_backup",
        "calculator": "refund_calculator",
        "order_lookup": "order_lookup_backup",
    }
    assert "customer_lookup" not in SUBSTITUTES
    assert "policy_lookup" not in SUBSTITUTES


def test_schema_listing_includes_every_tool() -> None:
    schemas = list_schemas(build_registry())

    assert set(schemas) == set(build_registry())
    assert schemas["order_lookup"]["properties"]["order_id"]["pattern"] == "^O\\d{3}$"


def test_primary_tools_return_deterministic_outputs() -> None:
    world = default_world()
    registry = build_registry(world)
    order = world.orders["O001"]
    first_item = order.items[0]

    assert registry["customer_lookup"].call({"customer_id": order.customer_id}).ok
    assert registry["order_lookup"].call({"order_id": order.order_id}).output["subtotal"] == order.subtotal
    assert registry["inventory_lookup"].call({"sku": first_item.sku}).output["sku"] == first_item.sku

    shipping = registry["shipping_estimator"].call(
        {"zip": order.shipping_zip, "weight": first_item.weight}
    )
    assert shipping.ok
    assert shipping.output == registry["shipping_estimator"].call(
        {"zip": order.shipping_zip, "weight": first_item.weight}
    ).output

    calculation = registry["calculator"].call({"expression": "10 + 2 * 3"})
    assert calculation.ok
    assert calculation.output["result"] == 16.0


def test_evidence_checker_resolves_highest_confidence_source() -> None:
    checker = build_registry()["evidence_checker"]
    result = checker.call(
        {
            "claim": "The order is shipped",
            "sources": [
                {"source": "email", "value": "processing", "confidence": 0.4},
                {"source": "order_system", "value": "shipped", "confidence": 0.95},
            ],
        }
    )

    assert result.ok
    assert result.output["supported"] is True
    assert result.output["resolved_value"] == "shipped"
    assert result.output["conflicts"] == ["processing", "shipped"]


def test_every_tool_rejects_invalid_arguments_with_schema_error() -> None:
    for tool in build_registry().values():
        result = tool.call({})

        assert not result.ok
        assert result.error is not None
        assert result.error.startswith("schema_error:")
