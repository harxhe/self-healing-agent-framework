from __future__ import annotations

from healagent.data.generator import generate_world


def test_generate_world_is_deterministic() -> None:
    a = generate_world(seed=123).model_dump(mode="json")
    b = generate_world(seed=123).model_dump(mode="json")
    assert a == b


def test_generate_world_changes_with_seed() -> None:
    a = generate_world(seed=123).model_dump(mode="json")
    b = generate_world(seed=124).model_dump(mode="json")
    assert a != b


def test_world_has_expected_catalog_sizes_and_consistency() -> None:
    world = generate_world()

    assert len(world.customers) == 50
    assert len(world.orders) == 50
    assert len(world.skus) == 50

    for order in world.orders.values():
        assert order.customer_id in world.customers
        assert order.subtotal == round(
            sum(item.quantity * item.unit_price for item in order.items),
            2,
        )
        for item in order.items:
            sku = world.skus[item.sku]
            assert item.unit_price == sku.price
            assert item.weight == sku.weight

    refund_policy = world.policy.topics["refund"]
    assert refund_policy["refund_window_days"] == world.policy.refund_window_days
    assert refund_policy["restocking_fee_rate"] == world.policy.restocking_fee_rate
