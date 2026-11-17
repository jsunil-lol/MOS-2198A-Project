"""Run the fictional Supplier Rescue AI scenario from the command line."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from impact import CustomerOrder, RecoveryOption, RecoveryResult, Shipment, analyze_disruption


DATA_DIR = Path(__file__).resolve().parent / "data"


def main() -> None:
    scenario = json.loads((DATA_DIR / "demo_scenario.json").read_text(encoding="utf-8"))
    notice = (DATA_DIR / "sample_delay_email.txt").read_text(encoding="utf-8")
    purchase_order = scenario["purchase_order"]
    part_number = scenario["component"]["part_number"]
    on_hand = scenario["inventory"]["on_hand"]
    currency = scenario["currency"]
    orders = [
        CustomerOrder(row["order_id"], row["quantity"], date.fromisoformat(row["due_on"]))
        for row in scenario["customer_orders"]
    ]
    orders_by_id = {order.order_id: order for order in orders}
    delayed_shipment = Shipment(
        purchase_order["quantity"],
        date.fromisoformat(purchase_order["revised_arrival_on"]),
        Decimal(purchase_order["unit_cost"]),
    )
    offers = [
        RecoveryOption(
            row["supplier"],
            Shipment(
                row["quantity"], date.fromisoformat(row["arrives_on"]), Decimal(row["unit_cost"])
            ),
            Decimal(row["extra_fees"]),
        )
        for row in scenario["replacement_offers"]
    ]
    analysis = analyze_disruption(
        as_of=date.fromisoformat(scenario["as_of"]),
        on_hand=on_hand,
        orders=orders,
        delayed_shipment=delayed_shipment,
        options=offers,
    )

    print("Supplier Rescue AI — Fictional demo")
    print(f"\nSupplier notice\n{notice.rstrip()}")
    print("\nDelay details (preloaded from the fictional scenario)")
    print(
        f"{purchase_order['po_number']} | {part_number} | {delayed_shipment.quantity} units\n"
        f"Original delivery: {purchase_order['original_arrival_on']}\n"
        f"Revised delivery:  {delayed_shipment.arrives_on}\n"
        f"On hand: {on_hand} units as of {scenario['as_of']}"
    )

    print("\nRecovery options (calculated live)")
    waiting = RecoveryResult("Wait for original supplier", Decimal("0"), analysis.baseline)
    candidates = (waiting, *analysis.options)
    for candidate in candidates:
        print(f"\n{candidate.supplier} | Extra cost: {currency} {candidate.incremental_cost:.2f}")
        for order in candidate.orders:
            demand = orders_by_id[order.order_id]
            completion = (
                str(order.projected_fulfillment_on)
                if order.projected_fulfillment_on is not None
                else "insufficient confirmed supply"
            )
            print(
                f"  {order.order_id}: {order.shortage_at_due_date} units short by "
                f"{demand.due_on} | Complete: {completion}"
            )

    on_time = (
        candidate
        for candidate in candidates
        if all(order.shortage_at_due_date == 0 for order in candidate.orders)
    )
    recommendation = min(on_time, key=lambda candidate: candidate.incremental_cost, default=None)
    if recommendation is None:
        print("\nHuman review needed: every option misses at least one customer deadline.")
    else:
        print(
            f"\nRecommendation for human review: {recommendation.supplier}. "
            "It meets all customer deadlines at the lowest extra cost."
        )


if __name__ == "__main__":
    main()
