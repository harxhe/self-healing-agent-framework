"""Deterministic synthetic e-commerce data for the simulator."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from pydantic import BaseModel, Field

from healagent.core.seed import SeedManager

DEFAULT_DATA_SEED = 20261010
SIMULATION_TODAY = date(2026, 1, 15)


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    zip: str
    tier: str


class SKU(BaseModel):
    sku: str
    name: str
    category: str
    weight: float = Field(gt=0)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    warehouse_zip: str


class OrderItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    weight: float = Field(gt=0)


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[OrderItem]
    status: str
    order_date: date
    delivered_date: date | None
    eta_date: date | None
    tracking_number: str
    shipping_zip: str
    subtotal: float = Field(ge=0)


class PolicyTable(BaseModel):
    today: date
    refund_window_days: int
    restocking_fee_rate: float
    base_shipping: float
    per_lb_shipping: float
    expedited_surcharge: float
    standard_days_by_zone: dict[str, int]
    topics: dict[str, dict[str, object]]


class EcommerceWorld(BaseModel):
    customers: dict[str, Customer]
    orders: dict[str, Order]
    skus: dict[str, SKU]
    policy: PolicyTable


FIRST_NAMES = [
    "Avery",
    "Blake",
    "Casey",
    "Devon",
    "Emerson",
    "Finley",
    "Gray",
    "Harper",
    "Indigo",
    "Jordan",
]
LAST_NAMES = [
    "Brooks",
    "Chen",
    "Diaz",
    "Ellis",
    "Foster",
    "Gupta",
    "Hayes",
    "Iyer",
    "Kim",
    "Lopez",
]
ZIP_CODES = [
    "10001",
    "19103",
    "30301",
    "33101",
    "60601",
    "73301",
    "80202",
    "85001",
    "94105",
    "98101",
]
TIERS = ["standard", "silver", "gold", "platinum"]
PRODUCTS = [
    ("wireless mouse", "electronics"),
    ("travel mug", "home"),
    ("running socks", "apparel"),
    ("desk lamp", "home"),
    ("phone charger", "electronics"),
    ("notebook set", "office"),
    ("yoga mat", "fitness"),
    ("coffee grinder", "kitchen"),
    ("rain jacket", "apparel"),
    ("packing cubes", "travel"),
]
STATUSES = ["delivered", "shipped", "processing", "delivered", "returned"]


def generate_world(seed: int = DEFAULT_DATA_SEED) -> EcommerceWorld:
    """Generate a complete, internally consistent synthetic shop world."""

    rng = SeedManager(seed).rng("data", "world")
    customers = _generate_customers(rng)
    skus = _generate_skus(rng)
    orders = _generate_orders(rng, customers, skus)
    policy = _generate_policy()
    return EcommerceWorld(customers=customers, orders=orders, skus=skus, policy=policy)


@lru_cache(maxsize=1)
def default_world() -> EcommerceWorld:
    """Return the canonical deterministic world used by default tools and tasks."""

    return generate_world()


def _generate_customers(rng: object) -> dict[str, Customer]:
    customers: dict[str, Customer] = {}
    first_offset = int(rng.integers(0, len(FIRST_NAMES)))
    last_offset = int(rng.integers(0, len(LAST_NAMES)))
    for idx in range(50):
        first = FIRST_NAMES[(idx + first_offset) % len(FIRST_NAMES)]
        last = LAST_NAMES[(idx * 3 + last_offset) % len(LAST_NAMES)]
        customer_id = f"C{idx + 1:03d}"
        customers[customer_id] = Customer(
            customer_id=customer_id,
            name=f"{first} {last}",
            email=f"{first.lower()}.{last.lower()}{idx + 1:03d}@example.test",
            zip=ZIP_CODES[(idx * 7 + first_offset) % len(ZIP_CODES)],
            tier=TIERS[(idx + last_offset) % len(TIERS)],
        )
    return customers


def _generate_skus(rng: object) -> dict[str, SKU]:
    skus: dict[str, SKU] = {}
    product_offset = int(rng.integers(0, len(PRODUCTS)))
    for idx in range(50):
        base_name, category = PRODUCTS[(idx + product_offset) % len(PRODUCTS)]
        sku = f"SKU{idx + 1:03d}"
        weight = round(float(rng.uniform(0.25, 12.0)), 2)
        price = round(float(rng.uniform(8.0, 240.0)), 2)
        stock = int((idx * 11 + int(weight * 10)) % 83)
        skus[sku] = SKU(
            sku=sku,
            name=f"{base_name} {idx + 1}",
            category=category,
            weight=weight,
            price=price,
            stock=stock,
            warehouse_zip=ZIP_CODES[(idx * 5 + product_offset) % len(ZIP_CODES)],
        )
    return skus


def _generate_orders(
    rng: object,
    customers: dict[str, Customer],
    skus: dict[str, SKU],
) -> dict[str, Order]:
    orders: dict[str, Order] = {}
    sku_ids = list(skus)
    customer_ids = list(customers)
    order_offset = int(rng.integers(0, len(sku_ids)))

    for idx in range(50):
        order_id = f"O{idx + 1:03d}"
        customer = customers[customer_ids[(idx * 5 + order_offset) % len(customer_ids)]]
        item_count = 1 + (idx % 3)
        items: list[OrderItem] = []
        for item_idx in range(item_count):
            sku = skus[sku_ids[(idx * 7 + item_idx * 13 + order_offset) % len(sku_ids)]]
            quantity = 1 + ((idx + item_idx) % 3)
            items.append(
                OrderItem(
                    sku=sku.sku,
                    quantity=quantity,
                    unit_price=sku.price,
                    weight=sku.weight,
                )
            )

        subtotal = round(sum(item.quantity * item.unit_price for item in items), 2)
        status = STATUSES[idx % len(STATUSES)]
        order_date = SIMULATION_TODAY - timedelta(days=3 + (idx * 2) % 58)
        delivered_date = _delivered_date(idx, status, order_date)
        eta_date = None if delivered_date else SIMULATION_TODAY + timedelta(days=1 + idx % 7)

        orders[order_id] = Order(
            order_id=order_id,
            customer_id=customer.customer_id,
            items=items,
            status=status,
            order_date=order_date,
            delivered_date=delivered_date,
            eta_date=eta_date,
            tracking_number=f"TRK{idx + 1:08d}",
            shipping_zip=customer.zip,
            subtotal=subtotal,
        )

    return orders


def _delivered_date(idx: int, status: str, order_date: date) -> date | None:
    if status == "delivered":
        return order_date + timedelta(days=3 + idx % 4)
    if status == "returned":
        return order_date + timedelta(days=4 + idx % 3)
    return None


def _generate_policy() -> PolicyTable:
    refund_window_days = 30
    restocking_fee_rate = 0.15
    return PolicyTable(
        today=SIMULATION_TODAY,
        refund_window_days=refund_window_days,
        restocking_fee_rate=restocking_fee_rate,
        base_shipping=5.25,
        per_lb_shipping=1.18,
        expedited_surcharge=9.75,
        standard_days_by_zone={
            "1": 2,
            "2": 2,
            "3": 3,
            "4": 3,
            "5": 4,
            "6": 4,
            "7": 5,
            "8": 5,
            "9": 6,
        },
        topics={
            "refund": {
                "refund_window_days": refund_window_days,
                "restocking_fee_rate": restocking_fee_rate,
                "eligible_statuses": ["delivered", "returned"],
            },
            "shipping": {
                "base_shipping": 5.25,
                "per_lb_shipping": 1.18,
                "expedited_surcharge": 9.75,
                "standard_days_by_zone": {
                    "1": 2,
                    "2": 2,
                    "3": 3,
                    "4": 3,
                    "5": 4,
                    "6": 4,
                    "7": 5,
                    "8": 5,
                    "9": 6,
                },
            },
            "restocking": {
                "restocking_fee_rate": restocking_fee_rate,
                "waived_for_tiers": ["gold", "platinum"],
            },
            "replacement": {
                "requires_stock": True,
                "ship_with_standard_service": True,
            },
        },
    )
