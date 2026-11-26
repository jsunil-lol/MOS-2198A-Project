"""Tests for the email-to-explanation pipeline (pipeline.py).

Claude and the calculation step are both replaced by fakes, so no API key or
money is needed. Whether the REAL impact.py works with this is a separate
integration check, done once the branches are joined.

Run from the project folder:
    python -m unittest -v test_pipeline
"""

import json
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

from email_extraction import DelayFacts
from pipeline import explain_from_facts, handle_delay_email

GOOD_FACTS = {
    "supplier": "Maple Industrial Parts",
    "po_number": "PO-2841",
    "part_number": "BRG-6204",
    "affected_quantity": 100,
    "original_arrival_on": "2026-11-19",
    "revised_arrival_on": "2026-11-23",
}

EXPLANATION = {
    "recommendation": "Order from Northline Bearings; it costs 120.00 extra.",
    "supplier_email_draft": "Hi Maple, we will wait for the shipment.",
    # No customer names are passed, so the order is its own customer.
    "customer_emails": [{"customer": "CO-1001", "email": "Hi, order CO-1001 was at risk."}],
}

# Matches the real impact.py output for data/demo_scenario.json (trimmed to
# one order): waiting leaves CO-1001 60 short; Northline meets the deadline.
ANALYSIS = NS(
    baseline=(NS(order_id="CO-1001", shortage_at_due_date=60,
                 projected_fulfillment_on=date(2026, 11, 23)),),
    options=(NS(supplier="Northline Bearings", incremental_cost=Decimal("120.00"),
                orders=(NS(order_id="CO-1001", shortage_at_due_date=0,
                           projected_fulfillment_on=date(2026, 11, 19)),)),),
)


class FakeClaude:
    """Answers the extraction call first, then the explanation call."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, prompt, system="", max_tokens=1000):
        self.calls += 1
        return self.replies.pop(0)


class FakeBuilder:
    """Stands in for the app's function that runs impact.py."""

    def __init__(self, result=ANALYSIS):
        self.result = result
        self.received = []

    def __call__(self, facts):
        self.received.append(facts)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class HandleDelayEmailTests(unittest.TestCase):
    def test_clean_email_runs_every_step(self):
        # Breaks if: a step is skipped or the results are not handed on.
        fake = FakeClaude(json.dumps(GOOD_FACTS), json.dumps(EXPLANATION))
        builder = FakeBuilder()

        result = handle_delay_email("some email", builder, ask=fake)

        self.assertFalse(result.needs_review)
        self.assertEqual(result.facts.po_number, "PO-2841")
        self.assertIs(result.analysis, ANALYSIS)
        self.assertEqual(result.explanation.recommendation, EXPLANATION["recommendation"])
        self.assertEqual(fake.calls, 2)
        self.assertEqual(builder.received, [result.facts])

    def test_flagged_facts_stop_before_any_calculation_or_explanation(self):
        # Breaks if: the calculation runs on a guess (revised date missing).
        bad = {**GOOD_FACTS, "revised_arrival_on": None}
        fake = FakeClaude(json.dumps(bad))
        builder = FakeBuilder()

        result = handle_delay_email("some email", builder, ask=fake)

        self.assertTrue(result.needs_review)
        self.assertTrue(result.facts.needs_review)
        self.assertEqual(builder.received, [])
        self.assertEqual(fake.calls, 1)  # only the extraction call, no explanation
        self.assertIsNone(result.analysis)
        self.assertIsNone(result.explanation)
        self.assertTrue(result.issues)

    def test_flagged_explanation_flags_the_whole_result(self):
        # Breaks if: an invented number in the draft is hidden from the screen.
        invented = {**EXPLANATION, "recommendation": "It will cost 450 extra."}
        fake = FakeClaude(json.dumps(GOOD_FACTS), json.dumps(invented))

        result = handle_delay_email("some email", FakeBuilder(), ask=fake)

        self.assertTrue(result.needs_review)
        self.assertTrue(any("450" in issue for issue in result.issues))
        self.assertEqual(result.explanation.recommendation, "It will cost 450 extra.")


class ExplainFromFactsTests(unittest.TestCase):
    def corrected_facts(self):
        # What a person types in after fixing a flagged email.
        return DelayFacts("Maple Industrial Parts", "PO-2841", "BRG-6204", 100,
                          date(2026, 11, 19), date(2026, 11, 23), False, ())

    def test_corrected_facts_go_straight_to_calculation_and_explanation(self):
        # Breaks if: fixing the facts by hand forces a second paid email read.
        fake = FakeClaude(json.dumps(EXPLANATION))
        builder = FakeBuilder()

        result = explain_from_facts(self.corrected_facts(), builder, ask=fake)

        self.assertFalse(result.needs_review)
        self.assertIs(result.analysis, ANALYSIS)
        self.assertEqual(fake.calls, 1)

    def test_still_flagged_facts_are_refused(self):
        # Breaks if: facts that are still incomplete reach the calculation.
        facts = DelayFacts(None, None, None, None, None, None, True, ("missing",))
        builder = FakeBuilder()

        result = explain_from_facts(facts, builder, ask=FakeClaude())

        self.assertTrue(result.needs_review)
        self.assertEqual(builder.received, [])
        self.assertIsNone(result.analysis)

    def test_a_calculation_error_is_flagged_not_raised(self):
        # Breaks if: bad inputs to impact.py (it raises ValueError) crash the demo.
        builder = FakeBuilder(ValueError("Customer order IDs must be unique"))
        fake = FakeClaude()

        result = explain_from_facts(self.corrected_facts(), builder, ask=fake)

        self.assertTrue(result.needs_review)
        self.assertTrue(any("unique" in issue for issue in result.issues))
        self.assertIsNone(result.explanation)
        self.assertEqual(fake.calls, 0)


if __name__ == "__main__":
    unittest.main()
