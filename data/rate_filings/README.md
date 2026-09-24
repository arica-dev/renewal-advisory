# Rate filings

`pa_small_group_2027.csv`: every Pennsylvania small-group (ACA single risk pool)
rate filing for plan year 2027 listed on https://ratereview.healthcare.gov/
(State: Pennsylvania, Small Group, 2027; 16 entries), retrieved 2026-09-24.

- `requested_pct` is the issuer's **requested** average rate change. All 16
  were "Submission Filed" with no final rate yet, so `final_pct` is blank.
  Regulators often approve less than requested.
- `range_low_pct` / `range_high_pct` are the site's "Current Range of Rate
  Change" across that issuer's products.
- Re-check before relying on it. Final rates will be published later in the cycle.
