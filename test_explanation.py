"""Tests for the recovery explanation (explanation.py).

Claude is replaced by a fake `ask` function, so no API key or money is needed.
These check what OUR code does with good and bad replies. They cannot show how
well real Claude writes; that needs a live test with an API key.

The analysis objects below copy the field names of impact.py (on the
order-impact-calculations branch) so this file does not depend on that branch.

Run from the project folder:
    python -m unittest -v test_explanation
"""

import json
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

import claude_client
from explanation import explain_recovery


def impact(order_id, shortage, fulfilled_on):
    return NS(order_id=order_id, shortage_at_due_date=shortage,
              projected_fulfillment_on=fulfilled_on)


# Hand-built from data/demo_scenario.json: waiting for Maple leaves CO-1001
# 100 units short (arrives Nov 23); Northline fixes 60 of them at a cost of 120.00.
ANALYSIS = NS(
    baseline=(
        impact("CO-1001", 100, date(2026, 11, 23)),
        impact("CO-1002", 40, date(2026, 11, 23)),
    ),
    options=(
        NS(supplier="Northline Bearings", incremental_cost=Decimal("120.00"),
           orders=(impact("CO-1001", 40, date(2026, 11, 23)),
                   impact("CO-1002", 0, date(2026, 11, 23)))),
        NS(supplier="Lakeshore Components", incremental_cost=Decimal("40.00"),
           orders=(impact("CO-1001", 60, date(2026, 11, 23)),
                   impact("CO-1002", 0, date(2026, 11, 23)))),
    ),
)

GOOD_REPLY = {
    "recommendation": "Order from Northline Bearings. It costs 120.00 extra and cuts "
                      "the CO-1001 shortage from 100 to 40 units.",
    "supplier_email_draft": "Hi Maple, we will wait for the 100 units due 2026-11-23.",
    "customer_email_draft": "Hi, order CO-1001 is delayed; 40 units are short.",
}


def reply_with(**changes):
    return json.dumps({**GOOD_REPLY, **changes})


class FakeClaude:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, prompt, system="", max_tokens=1000):
        self.calls.append({"prompt": prompt, "system": system})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class GoodExplanationTests(unittest.TestCase):
    def test_good_reply_gives_three_texts_and_no_flag(self):
        # Breaks if: a text is dropped or a correct explanation is flagged.
        result = explain_recovery(ANALYSIS, ask=FakeClaude(json.dumps(GOOD_REPLY)))

        self.assertEqual(result.recommendation, GOOD_REPLY["recommendation"])
        self.assertEqual(result.supplier_email_draft, GOOD_REPLY["supplier_email_draft"])
        self.assertEqual(result.customer_email_draft, GOOD_REPLY["customer_email_draft"])
        self.assertFalse(result.needs_review)
        self.assertEqual(result.issues, ())

    def test_claude_is_given_the_calculated_numbers(self):
        # Breaks if: the figures from impact.py are not sent, so Claude would
        # have to invent them.
        fake = FakeClaude(json.dumps(GOOD_REPLY))

        explain_recovery(ANALYSIS, ask=fake)

        self.assertEqual(len(fake.calls), 1)
        prompt = fake.calls[0]["prompt"]
        for must_appear in ("Northline Bearings", "120.00", "Lakeshore Components",
                            "40.00", "CO-1001", "2026-11-23"):
            self.assertIn(must_appear, prompt)
        self.assertTrue(fake.calls[0]["system"].strip())

    def test_a_number_written_in_another_format_is_not_flagged(self):
        # Breaks if: "120" or "$120.0" is flagged when the data says 120.00.
        reply = reply_with(recommendation="Northline costs $120 extra; 40.0 units remain short.")

        result = explain_recovery(ANALYSIS, ask=FakeClaude(reply))

        self.assertFalse(result.needs_review)


class InventedNumberTests(unittest.TestCase):
    def test_a_number_not_in_the_data_is_flagged(self):
        # Breaks if: Claude can quote "$450" or "75 units" that no calculation produced.
        for field in ("recommendation", "supplier_email_draft", "customer_email_draft"):
            with self.subTest(field=field):
                reply = reply_with(**{field: "This will cost 450 extra."})

                result = explain_recovery(ANALYSIS, ask=FakeClaude(reply))

                self.assertTrue(result.needs_review)
                self.assertTrue(any("450" in issue for issue in result.issues))

    def test_the_numbers_are_flagged_but_the_text_is_still_returned(self):
        # Breaks if: a flagged draft is thrown away so the person cannot fix it.
        reply = reply_with(recommendation="Costs 450 extra.")

        result = explain_recovery(ANALYSIS, ask=FakeClaude(reply))

        self.assertEqual(result.recommendation, "Costs 450 extra.")


class BadReplyTests(unittest.TestCase):
    def test_reply_that_is_not_json_is_flagged_with_empty_texts(self):
        # Breaks if: a chatty reply crashes the app or is shown half-parsed.
        result = explain_recovery(ANALYSIS, ask=FakeClaude("Here is my advice..."))

        self.assertTrue(result.needs_review)
        self.assertEqual(result.recommendation, "")

    def test_reply_missing_a_text_is_flagged(self):
        # Breaks if: a missing customer draft is silently shown as blank.
        partial = json.dumps({"recommendation": "Order from Northline Bearings."})

        result = explain_recovery(ANALYSIS, ask=FakeClaude(partial))

        self.assertTrue(result.needs_review)
        self.assertTrue(any("customer_email_draft" in issue for issue in result.issues))

    def test_missing_api_key_is_flagged_with_a_clear_message(self):
        # Breaks if: running without a key crashes the screen.
        fake = FakeClaude(claude_client.MissingApiKeyError("no key"))

        result = explain_recovery(ANALYSIS, ask=fake)

        self.assertTrue(result.needs_review)
        self.assertTrue(any("API key" in issue for issue in result.issues))

    def test_other_claude_errors_are_flagged_not_raised(self):
        # Breaks if: a network error crashes the demo mid-presentation.
        result = explain_recovery(ANALYSIS, ask=FakeClaude(RuntimeError("timeout")))

        self.assertTrue(result.needs_review)
        self.assertEqual(result.customer_email_draft, "")


if __name__ == "__main__":
    unittest.main()
