import subprocess
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from impact import CustomerOrder, OrderImpact, RecoveryOption, Shipment, analyze_disruption


WEDNESDAY = date(2026, 11, 18)
THURSDAY = date(2026, 11, 19)
FRIDAY = date(2026, 11, 20)
MONDAY = date(2026, 11, 23)


class DisruptionAnalysisTests(unittest.TestCase):
    def analyze(self, *options):
        return analyze_disruption(
            as_of=WEDNESDAY,
            on_hand=40,
            orders=[
                CustomerOrder("Monday order", 40, MONDAY),
                CustomerOrder("Friday order", 100, FRIDAY),
            ],
            delayed_shipment=Shipment(100, MONDAY, Decimal("10")),
            options=options,
        )

    def test_earliest_due_order_has_a_60_unit_shortage(self):
        self.assertEqual(
            self.analyze().baseline,
            (
                OrderImpact("Friday order", 60, MONDAY),
                OrderImpact("Monday order", 0, MONDAY),
            ),
        )

    def test_compares_fast_and_late_suppliers_independently(self):
        result = self.analyze(
            RecoveryOption("Fast supplier", Shipment(60, THURSDAY, Decimal("12"))),
            RecoveryOption("Late supplier", Shipment(60, MONDAY, Decimal("11"))),
        )
        fast, late = result.options
        self.assertEqual(fast.incremental_cost, Decimal("120"))
        self.assertEqual(
            fast.orders,
            (
                OrderImpact("Friday order", 0, THURSDAY),
                OrderImpact("Monday order", 0, MONDAY),
            ),
        )
        self.assertEqual(late.incremental_cost, Decimal("60"))
        self.assertEqual(late.orders, result.baseline)

    def test_partial_recovery_and_extra_fees(self):
        (option,) = self.analyze(
            RecoveryOption(
                "Partial supplier", Shipment(30, THURSDAY, Decimal("12")), Decimal("25")
            )
        ).options
        self.assertEqual(option.incremental_cost, Decimal("85"))
        self.assertEqual(option.orders[0], OrderImpact("Friday order", 30, MONDAY))

    def test_reports_when_known_supply_cannot_fill_an_order(self):
        result = analyze_disruption(
            as_of=WEDNESDAY,
            on_hand=0,
            orders=[CustomerOrder("Friday order", 110, FRIDAY)],
            delayed_shipment=Shipment(100, MONDAY, Decimal("10")),
        )
        self.assertEqual(result.baseline, (OrderImpact("Friday order", 110, None),))

    def test_rejects_replacement_above_delayed_quantity(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            self.analyze(
                RecoveryOption("Oversized order", Shipment(101, THURSDAY, Decimal("12")))
            )


class DemoScriptTests(unittest.TestCase):
    def test_runs_the_fictional_scenario_from_the_submitted_files(self):
        project = Path(__file__).resolve().parent
        result = subprocess.run(
            [sys.executable, str(project / "demo.py")],
            cwd=project / "data",
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        output = result.stdout
        self.assertIn("Subject: Delivery delay for PO-2841 (BRG-6204)", output)
        self.assertIn("Delay details (preloaded from the fictional scenario)", output)
        self.assertIn(
            "Wait for original supplier | Extra cost: CAD 0.00\n"
            "  CO-1001: 60 units short by 2026-11-20 | Complete: 2026-11-23\n"
            "  CO-1002: 0 units short by 2026-11-23 | Complete: 2026-11-23",
            output,
        )
        self.assertIn(
            "Northline Bearings | Extra cost: CAD 120.00\n"
            "  CO-1001: 0 units short by 2026-11-20 | Complete: 2026-11-19\n"
            "  CO-1002: 0 units short by 2026-11-23 | Complete: 2026-11-23",
            output,
        )
        self.assertIn(
            "Lakeshore Components | Extra cost: CAD 60.00\n"
            "  CO-1001: 60 units short by 2026-11-20 | Complete: 2026-11-23\n"
            "  CO-1002: 0 units short by 2026-11-23 | Complete: 2026-11-23",
            output,
        )
        self.assertIn("Recommendation for human review: Northline Bearings.", output)


if __name__ == "__main__":
    unittest.main()
