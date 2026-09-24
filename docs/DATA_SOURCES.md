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

## Carrier rate filings (your step, day 1)
CMS publishes Unified Rate Review data as public-use CSVs (plan years
2014-2026), covering single-risk-pool filings, which include small group:
https://www.cms.gov/marketplace/resources/data/rate-review-data
Search tool: https://ratereview.healthcare.gov/

Useful Worksheet 2 fields (per URRT instructions):
- "Cumulative Rate Change % (over 12 months prior)" by plan
- "Product Rate Increase %" and "Submission Level Rate Increase %"

To do:
1. Download the latest ZIP, filter to your state + market = small group.
2. Pick one carrier and note its submission-level and product-level increase.
3. Put that number in `FILED_AVG_PCT` in scripts/demo.py (now a placeholder).

Caveat: small-group carriers can file quarterly changes, and a filed average
is market-wide. Present it as a benchmark, not proof.

## Clasp API (field names used)
- Members: https://docs.withclasp.com/api-reference/members/post-members.md
- Dependents: https://docs.withclasp.com/api-reference/dependents/post-dependents.md
- Plans: https://docs.withclasp.com/api-reference/plans/post-plans.md
- Premiums: https://docs.withclasp.com/api-reference/plans/post-plan-premiums.md
- Age-banded table (21-year-old rate + state): https://docs.withclasp.com/api-reference/premiums/post-age-banded-table.md
- Contribution strategy: https://docs.withclasp.com/api-reference/plan_configurations/2026-04-24/post-plan-configurations-contribution_strategy.md
