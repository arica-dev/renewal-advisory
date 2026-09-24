# Data sources

## Age curve (in code)
Federal default ACA age curve, plan years 2018+: 0.765 (ages 0-14) up to
3.000 (64+). Verified against:
- CMS, State Specific Age Curve Variations:
  https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-market-reforms/downloads/statespecagecrv053117.pdf
- KFF copy of the 2018 HHS age factors:
  https://kff.org/wp-content/uploads/sites/3/2017/10/sbm_2018_age_sloping_170926.pdf

States with their own curve (DC, MA, MN, NJ, OR, UT) or no age rating
(NY, VT) are refused by `age_factor` until their curve is added.
Pennsylvania is the working default: close to Clasp (NYC) and on the default
curve. Confirm before relying on it.

## Carrier rate filings (done)
`data/rate_filings/pa_small_group_2027.csv` holds all 16 Pennsylvania
small-group filings for plan year 2027 from https://ratereview.healthcare.gov/,
retrieved 2026-09-24. All are *requested* changes (status "Submission Filed");
final rates weren't published yet. Median requested increase: 14.47%
(range 3.74% to 28.38%). See data/rate_filings/README.md.

CMS also publishes the underlying Unified Rate Review data as CSVs:
https://www.cms.gov/marketplace/resources/data/rate-review-data
Re-check when final rates are posted, and fill in `final_pct`.

## Clasp API (field names used)
- Members: https://docs.withclasp.com/api-reference/members/post-members.md
- Dependents: https://docs.withclasp.com/api-reference/dependents/post-dependents.md
- Plans: https://docs.withclasp.com/api-reference/plans/post-plans.md
- Premiums: https://docs.withclasp.com/api-reference/plans/post-plan-premiums.md
- Age-banded table (21-year-old rate + state): https://docs.withclasp.com/api-reference/premiums/post-age-banded-table.md
- Contribution strategy: https://docs.withclasp.com/api-reference/plan_configurations/2026-04-24/post-plan-configurations-contribution_strategy.md
