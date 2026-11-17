# Supplier delay demo

All suppliers, orders, and prices in this scenario are fictional.

- [demo_scenario.json](demo_scenario.json) contains the inventory snapshot, purchase order, customer orders, and replacement offers for part `BRG-6204`.
- [sample_delay_email.txt](sample_delay_email.txt) is the supplier notice to load into the demo screen. It identifies the purchase order, part, affected quantity, and revised arrival date.

The manufacturer assembles conveyor repair kits using one `BRG-6204` bearing per kit. It needs to complete 100 kits by Friday and another 40 by Monday. With 40 bearings on hand and the original shipment delayed to Monday, Friday's order is at risk. Both alternate offers are for approved replacements for `BRG-6204`. The scenario treats confirmed bearing availability as kit readiness because the bearing is the only part in short supply.

Use the scenario's fixed `as_of` date for the inventory snapshot. Dates are ISO calendar dates, quantities are in units, and prices and fees are decimal strings in CAD. The purchase order's `revised_arrival_on` is the delayed shipment date. Each replacement offer is evaluated independently and replaces the same number of units on the original purchase order. The original supplier credits those units at their original price.

## Expected results

| Option | Friday order `CO-1001` | Monday order `CO-1002` | Extra cost |
| --- | --- | --- | ---: |
| Wait for original supplier | 40 of 100 kits ready by Friday, complete Monday | Complete Monday | CAD 0.00 |
| Northline Bearings | All 100 kits ready Thursday | Complete Monday | CAD 120.00 |
| Lakeshore Components | 80 of 100 kits ready by Friday, complete Monday | Complete Monday | CAD 40.00 |

Lakeshore can deliver 40 bearings by Thursday at CAD 11.00 each, with delivery included. Its premium is 40 × CAD 1.00 = CAD 40.00. Northline can deliver 60 bearings by Thursday at CAD 11.50 each plus CAD 30.00 in rush freight. Its premium is 60 × CAD 1.50 + CAD 30.00 = CAD 120.00. Northline costs CAD 80.00 more than Lakeshore and gets the last 20 kits ready on time.

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
