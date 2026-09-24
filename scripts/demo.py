"""Generate the three sample groups and print a renewal breakdown for each.

Run:  python scripts/demo.py
"""

import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renewal_advisor.census import generate_group, write_census  # noqa: E402
from renewal_advisor.renewal import benchmark, break_down_renewal  # noqa: E402

RENEWAL_DATE = date(2027, 1, 1)
RATE_INCREASE = D("1.13")          # illustrative carrier base-rate change
FILED_AVG_PCT = D("11.0")          # placeholder: replace with the real filed figure

for size, seed in [(12, 1), (30, 2), (45, 3)]:
    g = generate_group(size, seed)
    write_census(g, ROOT / "data" / g.id)
    new_rates = {p.id: (p.base_rate_21 * RATE_INCREASE).quantize(D("0.01")) for p in g.plans}
    b = break_down_renewal(g, new_rates, RENEWAL_DATE)
    bm = benchmark(b, FILED_AVG_PCT)
    print(f"\n{g.name}: {len(g.enrolled_members)} enrolled")
    print(f"  Monthly premium  {b.current_monthly:>10,}  ->  {b.renewal_monthly:>10,}"
          f"   ({b.total_pct:+}%)")
    print(f"  From aging       {b.aging_effect:>10,}   ({b.aging_pct:+}% of current)")
    print(f"  From rate change {b.rate_effect:>10,}   ({b.rate_pct:+}% of current)")
    print(f"  Pure rate change {b.pure_rate_change_pct:+}% vs filed avg {bm.filed_avg_pct:+}%"
          f"  -> gap {bm.gap_pct:+} pts{'  [push back]' if bm.flag else ''}")
