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
from explanation import CustomerDraft, choose_recommendation, explain_recovery


def impact(order_id, shortage, fulfilled_on):
    return NS(order_id=order_id, shortage_at_due_date=shortage,
              projected_fulfillment_on=fulfilled_on)


# The real output of impact.py on data/demo_scenario.json (checked by running it).
# Waiting leaves CO-1001 60 units short. Northline fixes it at 120.00 extra;
# Lakeshore is cheaper (40.00) but leaves CO-1001 20 units short.
ANALYSIS = NS(
    baseline=(
        impact("CO-1001", 60, date(2026, 11, 23)),
        impact("CO-1002", 0, date(2026, 11, 23)),
    ),
    options=(
        NS(supplier="Northline Bearings", incremental_cost=Decimal("120.00"),
           orders=(impact("CO-1001", 0, date(2026, 11, 19)),
                   impact("CO-1002", 0, date(2026, 11, 23)))),
        NS(supplier="Lakeshore Components", incremental_cost=Decimal("40.00"),
           orders=(impact("CO-1001", 20, date(2026, 11, 23)),
                   impact("CO-1002", 0, date(2026, 11, 23)))),
    ),
)

SAME_CUSTOMER = {"CO-1001": "Acme Conveyors", "CO-1002": "Acme Conveyors"}
TWO_CUSTOMERS = {"CO-1001": "Acme Conveyors", "CO-1002": "Beta Mills"}


def option(supplier, cost, *shortages):
    """An option whose orders have the given shortages (for rule tests)."""
    orders = tuple(impact(f"CO-{i}", s, date(2026, 11, 23)) for i, s in enumerate(shortages, 1))
    return NS(supplier=supplier, incremental_cost=Decimal(cost), orders=orders)


def analysis_of(baseline_shortages, *options):
    baseline = tuple(impact(f"CO-{i}", s, date(2026, 11, 23))
                     for i, s in enumerate(baseline_shortages, 1))
    return NS(baseline=baseline, options=tuple(options))


CUSTOMER_EMAIL = ("Hi, order CO-1001 would have been 60 units short, but it is now "
                  "supplied on 2026-11-19.")

GOOD_REPLY = {
    "recommendation": "Order from Northline Bearings. It costs 120.00 extra and cuts "
                      "the CO-1001 shortage from 60 to 0 units.",
    "supplier_email_draft": "Hi Maple, we will wait for the rest of the shipment due 2026-11-23.",
    # With no customer names given, each order is its own customer.
    "customer_emails": [{"customer": "CO-1001", "email": CUSTOMER_EMAIL}],
}


def reply_with(**changes):
    """A Claude reply (as JSON text) that is GOOD_REPLY with some fields changed."""
    return json.dumps({**GOOD_REPLY, **changes})


def emails(*pairs):
    """The customer_emails part of a reply, from (customer, text) pairs."""
    return [{"customer": name, "email": text} for name, text in pairs]


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
    def test_good_reply_gives_the_texts_and_no_flag(self):
        # Breaks if: a text is dropped or a correct explanation is flagged.
        result = explain_recovery(ANALYSIS, ask=FakeClaude(json.dumps(GOOD_REPLY)))

        self.assertEqual(result.recommendation, GOOD_REPLY["recommendation"])
        self.assertEqual(result.supplier_email_draft, GOOD_REPLY["supplier_email_draft"])
        self.assertEqual(result.customer_email_drafts, (CustomerDraft("CO-1001", CUSTOMER_EMAIL),))
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
        reply = reply_with(recommendation="Northline Bearings costs $120 extra; 60.0 units are short if we wait.")

        result = explain_recovery(ANALYSIS, ask=FakeClaude(reply))

        self.assertFalse(result.needs_review)


class ChooseRecommendationTests(unittest.TestCase):
    def test_picks_the_cheapest_option_that_meets_every_deadline(self):
        # Breaks if: the cheaper-but-late Lakeshore (40.00, 20 short) wins, or
        # the on-time Northline is missed.
        chosen = choose_recommendation(ANALYSIS)

        self.assertEqual(chosen.supplier, "Northline Bearings")
        self.assertEqual(chosen.incremental_cost, Decimal("120.00"))
        self.assertFalse(chosen.is_waiting)

    def test_of_two_on_time_options_the_cheaper_wins(self):
        # Breaks if: the first on-time option wins instead of the cheapest.
        analysis = analysis_of((5,), option("Pricey", "90.00", 0), option("Cheap", "30.00", 0))

        self.assertEqual(choose_recommendation(analysis).supplier, "Cheap")

    def test_waiting_wins_when_it_already_meets_every_deadline(self):
        # Breaks if: a paid replacement is recommended when waiting costs nothing.
        analysis = analysis_of((0, 0), option("Northline Bearings", "120.00", 0, 0))

        chosen = choose_recommendation(analysis)

        self.assertTrue(chosen.is_waiting)
        self.assertEqual(chosen.incremental_cost, Decimal("0"))

    def test_an_equal_cost_tie_keeps_the_first_listed(self):
        # Breaks if: the answer changes between runs for the same data.
        analysis = analysis_of((5,), option("First", "50.00", 0), option("Second", "50.00", 0))

        self.assertEqual(choose_recommendation(analysis).supplier, "First")

    def test_no_option_meets_every_deadline_gives_none(self):
        # Breaks if: a late option is recommended as if it were fine.
        analysis = analysis_of((5,), option("Late A", "10.00", 1), option("Late B", "20.00", 3))

        self.assertIsNone(choose_recommendation(analysis))


class RecommendationInTheExplanationTests(unittest.TestCase):
    def test_claude_is_told_which_option_the_code_chose(self):
        # Breaks if: Claude has to pick the winner itself.
        fake = FakeClaude(json.dumps(GOOD_REPLY))

        explain_recovery(ANALYSIS, ask=fake)

        lines = [l for l in fake.calls[0]["prompt"].splitlines() if "ecommend" in l]
        self.assertTrue(any("Northline Bearings" in l for l in lines))
        self.assertFalse(any("Lakeshore" in l for l in lines))

    def test_result_reports_the_chosen_supplier(self):
        # Breaks if: the screen cannot show which option the code chose.
        result = explain_recovery(ANALYSIS, ask=FakeClaude(json.dumps(GOOD_REPLY)))

        self.assertEqual(result.recommended_supplier, "Northline Bearings")

    def test_recommendation_that_names_a_different_supplier_is_flagged(self):
        # Breaks if: Claude can quietly argue for Lakeshore instead.
        reply = reply_with(recommendation="Order from Lakeshore Components for 40.00 extra.")

        result = explain_recovery(ANALYSIS, ask=FakeClaude(reply))

        self.assertTrue(result.needs_review)
        self.assertTrue(any("Northline Bearings" in issue for issue in result.issues))

    def test_waiting_recommendation_must_say_to_wait(self):
        # Breaks if: a text that never mentions waiting passes when waiting is chosen.
        analysis = analysis_of((0, 0), option("Northline Bearings", "120.00", 0, 0))
        plain = {"supplier_email_draft": "Hi Maple, we will wait.", "customer_emails": []}
        says_wait = reply_with(recommendation="Wait for Maple's shipment; no extra cost.", **plain)
        says_buy = reply_with(recommendation="Buy from Northline Bearings.", **plain)

        self.assertFalse(explain_recovery(analysis, ask=FakeClaude(says_wait)).needs_review)
        self.assertTrue(explain_recovery(analysis, ask=FakeClaude(says_buy)).needs_review)

    def test_no_on_time_option_is_flagged_for_a_person_to_decide(self):
        # Breaks if: the demo implies a clean answer when every option is late.
        analysis = analysis_of((5,), option("Late A", "10.00", 1))
        reply = reply_with(recommendation="No option meets every deadline; a person must decide.")
        fake = FakeClaude(reply)

        result = explain_recovery(analysis, ask=fake)

        self.assertTrue(result.needs_review)
        self.assertIsNone(result.recommended_supplier)
        self.assertTrue(any("decide" in issue for issue in result.issues))
        self.assertIn("No option", fake.calls[0]["prompt"])
        self.assertEqual(result.customer_email_drafts, ())  # nothing is settled yet


class CustomerEmailTests(unittest.TestCase):
    def test_one_email_per_customer_covers_affected_and_unaffected_orders(self):
        # Breaks if: a customer with two orders gets two emails, or the email
        # drops the order that is fine (or the one that is not).
        text = ("Hi Acme, order CO-1001 would have been 60 units short but is now supplied "
                "on 2026-11-19. Order CO-1002 is not affected.")
        fake = FakeClaude(reply_with(customer_emails=emails(("Acme Conveyors", text))))

        result = explain_recovery(ANALYSIS, customers=SAME_CUSTOMER, ask=fake)

        self.assertEqual(result.customer_email_drafts, (CustomerDraft("Acme Conveyors", text),))
        self.assertFalse(result.needs_review)
        lines = {l.split(":")[0].strip(): l for l in fake.calls[0]["prompt"].splitlines()
                 if l.strip().startswith("Order CO-")}
        self.assertIn("AFFECTED", lines["Order CO-1001"])
        self.assertNotIn("NOT AFFECTED", lines["Order CO-1001"])
        self.assertIn("60", lines["Order CO-1001"])
        self.assertIn("NOT AFFECTED", lines["Order CO-1002"])

    def test_a_customer_with_no_affected_order_gets_no_email(self):
        # Breaks if: a customer whose order is fine is emailed (or sent to Claude).
        text = "Hi Acme, order CO-1001 would have been 60 units short but is now supplied."
        fake = FakeClaude(reply_with(customer_emails=emails(("Acme Conveyors", text))))

        result = explain_recovery(ANALYSIS, customers=TWO_CUSTOMERS, ask=fake)

        self.assertEqual([d.customer for d in result.customer_email_drafts], ["Acme Conveyors"])
        self.assertNotIn("Beta Mills", fake.calls[0]["prompt"])
        self.assertFalse(result.needs_review)

    def test_an_email_that_leaves_out_one_of_the_customers_orders_is_flagged(self):
        # Breaks if: the unaffected order CO-1002 can be silently omitted.
        text = "Hi Acme, order CO-1001 would have been 60 units short but is now supplied."
        reply = reply_with(customer_emails=emails(("Acme Conveyors", text)))

        result = explain_recovery(ANALYSIS, customers=SAME_CUSTOMER, ask=FakeClaude(reply))

        self.assertTrue(result.needs_review)
        self.assertTrue(any("CO-1002" in issue for issue in result.issues))

    def test_a_missing_customer_email_is_flagged_with_an_empty_draft(self):
        # Breaks if: a customer who needs an email silently gets none.
        result = explain_recovery(ANALYSIS, ask=FakeClaude(reply_with(customer_emails=[])))

        self.assertTrue(result.needs_review)
        self.assertEqual(result.customer_email_drafts, (CustomerDraft("CO-1001", ""),))
        self.assertTrue(any("CO-1001" in issue for issue in result.issues))

    def test_no_affected_customers_means_no_emails_and_no_flag(self):
        # Breaks if: nothing is wrong yet an email is demanded or the result is flagged.
        analysis = analysis_of((0, 0), option("Northline Bearings", "120.00", 0, 0))
        reply = reply_with(recommendation="Wait for Maple's shipment; no extra cost.",
                           supplier_email_draft="Hi Maple, we will wait.", customer_emails=[])
        fake = FakeClaude(reply)

        result = explain_recovery(analysis, ask=fake)

        self.assertEqual(result.customer_email_drafts, ())
        self.assertFalse(result.needs_review)
        self.assertIn("none", fake.calls[0]["prompt"].lower())


class InventedNumberTests(unittest.TestCase):
    def test_a_number_not_in_the_data_is_flagged(self):
        # Breaks if: Claude can quote "$450" or "75 units" that no calculation produced.
        cases = {
            "recommendation": {"recommendation": "Northline Bearings will cost 450 extra."},
            "supplier_email_draft": {"supplier_email_draft": "This will cost 450 extra."},
            "customer email": {"customer_emails": emails(("CO-1001", "Order CO-1001 costs 450 extra."))},
        }
        for name, change in cases.items():
            with self.subTest(field=name):
                result = explain_recovery(ANALYSIS, ask=FakeClaude(reply_with(**change)))

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
        self.assertEqual(result.customer_email_drafts, ())

    def test_reply_missing_a_text_is_flagged(self):
        # Breaks if: a missing supplier draft is silently shown as blank.
        partial = json.dumps({"recommendation": "Order from Northline Bearings.",
                              "customer_emails": emails(("CO-1001", CUSTOMER_EMAIL))})

        result = explain_recovery(ANALYSIS, ask=FakeClaude(partial))

        self.assertTrue(result.needs_review)
        self.assertTrue(any("supplier_email_draft" in issue for issue in result.issues))

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
        self.assertEqual(result.customer_email_drafts, ())


if __name__ == "__main__":
    unittest.main()
