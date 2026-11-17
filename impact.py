"""Estimate the impact of one delayed component and compare replacement shipments."""

from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional, Tuple


@dataclass(frozen=True)
class CustomerOrder:
    order_id: str
    quantity: int
    due_on: date


@dataclass(frozen=True)
class Shipment:
    quantity: int
    arrives_on: date
    unit_cost: Decimal


@dataclass(frozen=True)
class RecoveryOption:
    supplier: str
    shipment: Shipment
    extra_fees: Decimal = Decimal("0")


@dataclass(frozen=True)
class OrderImpact:
    order_id: str
    shortage_at_due_date: int
    projected_fulfillment_on: Optional[date]


@dataclass(frozen=True)
class RecoveryResult:
    supplier: str
    incremental_cost: Decimal
    orders: Tuple[OrderImpact, ...]


@dataclass(frozen=True)
class DisruptionAnalysis:
    baseline: Tuple[OrderImpact, ...]
    options: Tuple[RecoveryResult, ...]


def analyze_disruption(
    *,
    as_of: date,
    on_hand: int,
    orders: Iterable[CustomerOrder],
    delayed_shipment: Shipment,
    options: Iterable[RecoveryOption] = (),
) -> DisruptionAnalysis:
    """Compare waiting for the original shipment with each alternate supplier.

    All quantities refer to the same compatible component. Supply goes to the
    earliest due order first, with input order breaking ties. Each option is
    independent and replaces the same quantity from the delayed shipment.
    Incremental cost assumes the original purchase cost for those units is
    avoidable. Include any shipping or cancellation charges in extra_fees.
    """
    if on_hand < 0:
        raise ValueError("On-hand inventory cannot be negative")

    ordered_demand = sorted(orders, key=lambda order: order.due_on)
    if any(order.quantity <= 0 for order in ordered_demand):
        raise ValueError("Customer order quantities must be positive")
    if len({order.order_id for order in ordered_demand}) != len(ordered_demand):
        raise ValueError("Customer order IDs must be unique")

    _validate_shipment(delayed_shipment, as_of)
    baseline = _allocate(
        ordered_demand,
        [(as_of, on_hand), (delayed_shipment.arrives_on, delayed_shipment.quantity)],
    )

    results = []
    for option in options:
        shipment = option.shipment
        _validate_shipment(shipment, as_of)
        if shipment.quantity > delayed_shipment.quantity:
            raise ValueError("Replacement quantity cannot exceed the delayed quantity")
        if not option.extra_fees.is_finite() or option.extra_fees < 0:
            raise ValueError("Extra fees must be finite and non-negative")

        remaining_original = delayed_shipment.quantity - shipment.quantity
        incremental_cost = (
            (shipment.unit_cost - delayed_shipment.unit_cost) * shipment.quantity
            + option.extra_fees
        )
        impacts = _allocate(
            ordered_demand,
            [
                (as_of, on_hand),
                (delayed_shipment.arrives_on, remaining_original),
                (shipment.arrives_on, shipment.quantity),
            ],
        )
        results.append(RecoveryResult(option.supplier, incremental_cost, impacts))

    return DisruptionAnalysis(baseline, tuple(results))


def _validate_shipment(shipment: Shipment, as_of: date) -> None:
    if shipment.quantity <= 0:
        raise ValueError("Shipment quantities must be positive")
    if shipment.arrives_on < as_of:
        raise ValueError("Expected shipment dates cannot precede the inventory snapshot")
    if not shipment.unit_cost.is_finite() or shipment.unit_cost < 0:
        raise ValueError("Unit costs must be finite and non-negative")


def _allocate(
    orders: Iterable[CustomerOrder], supply: Iterable[Tuple[date, int]]
) -> Tuple[OrderImpact, ...]:
    available = deque(sorted((day, quantity) for day, quantity in supply if quantity))
    impacts = []
    for order in orders:
        remaining = order.quantity
        on_time = 0
        last_arrival = None
        while remaining and available:
            day, quantity = available.popleft()
            allocated = min(remaining, quantity)
            remaining -= allocated
            if day <= order.due_on:
                on_time += allocated
            if allocated < quantity:
                available.appendleft((day, quantity - allocated))
            last_arrival = day
        impacts.append(
            OrderImpact(
                order.order_id,
                order.quantity - on_time,
                last_arrival if remaining == 0 else None,
            )
        )
    return tuple(impacts)
