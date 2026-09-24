"""Public rate filings (ratereview.healthcare.gov) and the push-back benchmark.

The benchmark compares the *rate-driven* part of a group's renewal (aging
removed) with either one carrier's filing or the whole state market:

- above_range   : higher than anything that carrier (or any carrier) requested
- above_average : above the average / median requested increase
- within        : at or below it

Filings here are *requested* changes; regulators often approve less. A filed
average is a market-wide benchmark, not proof that one group's renewal is wrong.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import median

DEFAULT_FILINGS = (Path(__file__).resolve().parents[2] / "data" / "rate_filings"
                   / "pa_small_group_2027.csv")
SOURCE_URL = "https://ratereview.healthcare.gov/"


@dataclass(frozen=True)
class Filing:
    company: str
    effective_date: date
    requested_pct: Decimal
    final_pct: Decimal | None
    range_low_pct: Decimal
    range_high_pct: Decimal
    products: int
    status: str

    @property
    def rate_pct(self) -> Decimal:
        """Final rate if approved, otherwise the requested rate."""
        return self.final_pct if self.final_pct is not None else self.requested_pct

    @property
    def is_final(self) -> bool:
        return self.final_pct is not None


def load_filings(path: Path = DEFAULT_FILINGS) -> list[Filing]:
    with open(path, newline="") as f:
        return [Filing(
            company=r["company"], effective_date=date.fromisoformat(r["effective_date"]),
            requested_pct=Decimal(r["requested_pct"]),
            final_pct=Decimal(r["final_pct"]) if r["final_pct"] else None,
            range_low_pct=Decimal(r["range_low_pct"]),
            range_high_pct=Decimal(r["range_high_pct"]),
            products=int(r["products"]), status=r["status"]) for r in csv.DictReader(f)]


@dataclass(frozen=True)
class MarketSummary:
    count: int
    median_pct: Decimal
    low_pct: Decimal        # lowest carrier average
    high_pct: Decimal       # highest carrier average
    all_final: bool


def market_summary(filings: list[Filing]) -> MarketSummary:
    rates = [f.rate_pct for f in filings]
    return MarketSummary(len(filings), Decimal(str(median(rates))).quantize(Decimal("0.01")),
                         min(rates), max(rates), all(f.is_final for f in filings))


@dataclass(frozen=True)
class FilingBenchmark:
    against: str               # carrier name or market label
    group_rate_pct: Decimal    # this group's rate change, aging removed
    reference_pct: Decimal     # carrier average or market median
    range_low_pct: Decimal
    range_high_pct: Decimal
    requested: bool            # True if the reference is a requested (not final) rate

    @property
    def gap_pct(self) -> Decimal:
        return self.group_rate_pct - self.reference_pct

    @property
    def verdict(self) -> str:
        if self.group_rate_pct > self.range_high_pct:
            return "above_range"
        if self.group_rate_pct > self.reference_pct:
            return "above_average"
        return "within"


def against_carrier(group_rate_pct: Decimal, filing: Filing) -> FilingBenchmark:
    return FilingBenchmark(filing.company, group_rate_pct, filing.rate_pct,
                           filing.range_low_pct, filing.range_high_pct, not filing.is_final)


def against_market(group_rate_pct: Decimal, filings: list[Filing],
                   label: str = "Pennsylvania small-group market") -> FilingBenchmark:
    m = market_summary(filings)
    return FilingBenchmark(label, group_rate_pct, m.median_pct, m.low_pct, m.high_pct,
                           not m.all_final)
