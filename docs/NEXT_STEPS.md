# Next steps

## Before day 3
- [x] Get the real filed rate changes (all 16 PA small-group carriers, 2027).
- [ ] Build a small spreadsheet by hand for the 12-person group
      (data/grp_12_1/*.csv) and check it matches `scripts/demo.py` to the cent.
      This is an independent check, and it makes you fluent in the math.

## Day 3: scenario engine (done)
- `scenarios.py` prices accept-renewal, move-plan and contribution-change
  options per employee and compares each with today.
- Finding from the demo: moving everyone to Silver saves the employer money
  but raises costs for Bronze enrollees. That's why the recommender needs
  per-employee constraints.

## Day 5: recommender (done)
- Searches plan designs (keep current, or move everyone to one plan) x employer
  % for employee-only x employer % for tiers with dependents.
- Goals: max employer increase %, max monthly increase for any employee,
  carrier minimum contribution, optional max deductible.
- Default objective protects employees: within the employer budget, minimise
  the total cost pushed onto employees. `objective="lowest_employer_cost"`
  is the alternative.
- If fewer designs meet the goals than requested, it fills in the closest
  misses and shows what each one missed and by how much.
- Demo finding: with a 13% rate hike, a 5% employer budget is only reachable
  by moving to Bronze. With the deductible capped at $3,500, nothing meets
  the goals, so the benchmark push-back becomes the main lever.
- Open question: the "closest miss" score (% points over + dollars over / 10)
  is a judgment call. Ask a broker how they'd weigh the two.

## Day 6: UI + PDF extraction (done)
- `streamlit run app.py`. Sidebar: group, renewal PDF (auto-read, editable),
  filed average, today's contribution, goals. Main page: breakdown, benchmark,
  recommended options + chart, per-employee effect.
- `ingest.py` reads the sample carrier layout with pdfplumber and checks it
  against the group (wrong group, rate mismatches, missing plans).
- `extract_with_claude` is the fallback for other layouts. It isn't tested
  (needs an API key), and isn't wired into the app yet.

## Day 7: polish and ship
- [x] Real filings in the app: market median + range, or a specific carrier's
      average + product range, cited with source and retrieval date.
- [ ] Push to GitHub, deploy free on Streamlit Community Cloud
      (share.streamlit.io, uses requirements.txt), and send Zach the link.
- [ ] Record a 2-minute Loom: breakdown -> benchmark -> recommendation.
- [ ] Optional: AI-drafted client memo from the computed numbers.

## Open assumptions
- Same census and plan elections before and after renewal.
- Only `employer_percentage` and `flat_employer_cost` contribution types are
  implemented. How Clasp's `flat_employer_percentage` is defined is unconfirmed.
- Composite rating (Clasp `premium_type: composite`) isn't supported yet.
