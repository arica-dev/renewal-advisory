# Next steps

## Before day 3
- [ ] Get the real filed rate change for one PA carrier (docs/DATA_SOURCES.md).
- [ ] Build a small spreadsheet by hand for the 12-person group
      (data/grp_12_1/*.csv) and check it matches `scripts/demo.py` to the cent.
      This is an independent check, and it makes you fluent in the math.

## Day 3: scenario engine
- `scenarios.py`: given a group, renewal rates, alternative plans and a
  contribution strategy, return per-employee and total employer/employee cost.
- Scenarios: accept renewal, move everyone to plan X, change contribution %.

## Day 5: recommender
- Grid search: plans x employer contribution (e.g. 50-100% in 5% steps).
- Constraints: max employer increase %, max monthly increase per employee,
  carrier minimum contribution (often 50% of employee-only; confirm per carrier).
- Rank the feasible options, return the top 3.

## Day 6: UI
- Streamlit: upload census, enter renewal rates, see the breakdown card,
  benchmark, top options, and the per-employee table.

## Open assumptions
- Same census and plan elections before and after renewal.
- Only `employer_percentage` and `flat_employer_cost` contribution types are
  implemented. How Clasp's `flat_employer_percentage` is defined is unconfirmed.
- Composite rating (Clasp `premium_type: composite`) isn't supported yet.
