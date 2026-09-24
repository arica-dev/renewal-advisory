"""Synthetic census + CSV round-trip. All people, plans and rates are fictional."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .models import Dependent, Group, Member, Plan

FIRST = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
         "Avery", "Quinn", "Drew", "Reese", "Cameron", "Parker", "Rowan", "Skyler"]
LAST = ["Rivera", "Chen", "Patel", "Nguyen", "Okafor", "Kowalski", "Haddad",
        "Silva", "Novak", "Moreau", "Tanaka", "Byrne", "Lindqvist", "Abara"]

# Illustrative monthly rates for a 21-year-old. Not real carrier rates.
DEFAULT_PLANS = [
    dict(id="plan_gold", plan_name="Gold PPO 1500", carrier="Carrier A",
         metal_level="gold", deductible="1500", oop_max="6000", base_rate_21="520.00"),
    dict(id="plan_silver", plan_name="Silver HMO 3500", carrier="Carrier A",
         metal_level="silver", deductible="3500", oop_max="8000", base_rate_21="435.00"),
    dict(id="plan_bronze", plan_name="Bronze HSA 6000", carrier="Carrier A",
         metal_level="bronze", deductible="6000", oop_max="8550", base_rate_21="360.00"),
]


def _dob(rng: random.Random, age: int, as_of: date) -> date:
    return as_of - timedelta(days=int(age * 365.25) + rng.randint(1, 360))


def generate_group(size: int, seed: int = 0, state: str = "PA",
                   plan_year_start: date = date(2026, 1, 1),
                   name: str | None = None) -> Group:
    """Deterministic synthetic small group of `size` employees."""
    rng = random.Random(seed)
    plans = [Plan(state=state, **p) for p in DEFAULT_PLANS]
    plan_weights = [0.3, 0.5, 0.2]
    gid = f"grp_{size}_{seed}"
    members: list[Member] = []
    for i in range(size):
        age = rng.randint(22, 63)
        last = rng.choice(LAST)
        mid = f"{gid}_m{i:03d}"
        deps: list[Dependent] = []
        if age >= 26 and rng.random() < 0.45:
            deps.append(Dependent(id=f"{mid}_sp", first_name=rng.choice(FIRST), last_name=last,
                                  dob=_dob(rng, max(22, age + rng.randint(-5, 5)), plan_year_start),
                                  member_relationship="spouse"))
        if 26 <= age <= 55 and rng.random() < 0.4:
            for k in range(rng.choice([1, 1, 2, 2, 3, 4])):
                kid_age = rng.randint(0, min(25, age - 20))
                deps.append(Dependent(id=f"{mid}_c{k}", first_name=rng.choice(FIRST),
                                      last_name=last, dob=_dob(rng, kid_age, plan_year_start),
                                      member_relationship="child"))
        waived = rng.random() < 0.1
        members.append(Member(
            id=mid, first_name=rng.choice(FIRST), last_name=last,
            dob=_dob(rng, age, plan_year_start), employer=gid,
            hire_date=plan_year_start - timedelta(days=rng.randint(30, 3000)),
            state=state, zip_code="19103", dependents=deps,
            enrolled_plan=None if waived else rng.choices([p.id for p in plans], plan_weights)[0],
        ))
    return Group(id=gid, name=name or f"Sample Co ({size} employees)", state=state,
                 plan_year_start=plan_year_start, members=members, plans=plans)


def write_census(group: Group, folder: Path) -> None:
    """Write members.csv and dependents.csv (Clasp-style field names)."""
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "members.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "first_name", "last_name", "dob", "employer", "hire_date",
                    "state", "zip_code", "enrolled_plan"])
        for m in group.members:
            w.writerow([m.id, m.first_name, m.last_name, m.dob, m.employer, m.hire_date,
                        m.state, m.zip_code, m.enrolled_plan or ""])
    with open(folder / "dependents.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "member", "first_name", "last_name", "dob", "member_relationship"])
        for m in group.members:
            for d in m.dependents:
                w.writerow([d.id, m.id, d.first_name, d.last_name, d.dob, d.member_relationship])


def read_census(folder: Path, group_id: str, name: str, state: str,
                plan_year_start: date, plans: list[Plan]) -> Group:
    deps_by_member: dict[str, list[Dependent]] = {}
    with open(folder / "dependents.csv", newline="") as f:
        for row in csv.DictReader(f):
            member = row.pop("member")
            deps_by_member.setdefault(member, []).append(Dependent(**row))
    members = []
    with open(folder / "members.csv", newline="") as f:
        for row in csv.DictReader(f):
            row["enrolled_plan"] = row["enrolled_plan"] or None
            members.append(Member(**row, dependents=deps_by_member.get(row["id"], [])))
    return Group(id=group_id, name=name, state=state, plan_year_start=plan_year_start,
                 members=members, plans=plans)


def plans_with_rates(plans: list[Plan], rates: dict[str, Decimal]) -> list[Plan]:
    return [p.model_copy(update={"base_rate_21": rates[p.id]}) for p in plans]
