# Supplier delay demo

All suppliers, orders, and prices in this scenario are fictional.

- [demo_scenario.json](demo_scenario.json) contains the inventory snapshot, purchase order, customer orders, and replacement offers for part `BRG-6204`.
- [sample_delay_email.txt](sample_delay_email.txt) is the supplier notice to load into the demo screen. It identifies the purchase order, part, affected quantity, and revised arrival date.

Use the scenario's fixed `as_of` date for the inventory snapshot. Dates are ISO calendar dates, quantities are in units, and prices and fees are decimal strings in CAD. The purchase order's `revised_arrival_on` is the delayed shipment date. Each replacement offer is evaluated independently and replaces the same number of units on the original purchase order. The original supplier credits those units at their original price.

## Expected results

| Option | Friday order `CO-1001` | Monday order `CO-1002` | Extra cost |
| --- | --- | --- | ---: |
| Wait for original supplier | 60 units short on Friday, complete Monday | Complete Monday | CAD 0.00 |
| Northline Bearings | Complete Thursday | Complete Monday | CAD 120.00 |
| Lakeshore Components | 60 units short on Friday, complete Monday | Complete Monday | CAD 60.00 |

Both offers cover 60 units and carry no extra fees. Northline costs CAD 2.00 more per unit and protects the Friday deadline. Lakeshore costs CAD 1.00 more per unit and arrives Monday, the same day as the delayed shipment.

## Run the demo and tests

From the project folder, use Python 3.9 or newer.

```sh
python3 demo.py
python3 -m unittest -v test_impact
```

The script uses the Python standard library. It prints the sample email and preloaded delay details, then calculates order impacts and recovery costs live. It recommends the lowest-cost option that meets every deadline, including waiting when it meets those deadlines. If every option misses a deadline, the script calls for human review.

## Files for submission

Keep the project layout when submitting `demo.py`, `impact.py`, `test_impact.py`, and the three files in `data/` listed below.

```text
demo.py
impact.py
test_impact.py
data/
    README.md
    demo_scenario.json
    sample_delay_email.txt
```
