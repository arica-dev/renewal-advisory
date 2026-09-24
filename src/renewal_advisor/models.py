"""Core data models.

Field names mirror Clasp's public API (docs.withclasp.com) where an equivalent
exists, so this project maps cleanly onto their objects:

- Member / Dependent  -> Clasp members / dependents (dob, member_relationship, ...)
- Plan                -> Clasp plans (plan_name, line_of_coverage, premium_type)
- premium rates       -> Clasp's age-banded table is driven by a 21-year-old rate
                         + state, which is what `base_rate_21` holds here
- ContributionStrategy-> Clasp's `benefit_split` strategy keyed by coverage_type

Simplifications vs. Clasp: address is flattened to state/zip, and SSN and
other PII fields are omitted (synthetic data only).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class CoverageType(str, Enum):
    """Clasp coverage_type enum."""

    member = "member"
    member_spouse = "member_spouse"
    member_child = "member_child"
    member_children = "member_children"
    member_family = "member_family"


class RelationshipCategory(str, Enum):
    """Clasp relationship_category enum."""

    member = "member"
    spouse = "spouse"
    child = "child"


# Subset of Clasp's member_relationship enum, mapped to a rating category.
SPOUSE_LIKE = {"spouse", "domestic_partner", "civil_union"}
CHILD_LIKE = {"child", "step_child", "adopted_child", "foster_child", "grandchild",
              "legal_guardianship", "court_ordered_dependent"}


class Dependent(BaseModel):
    id: str
    first_name: str
    last_name: str
    dob: date
    member_relationship: str

    @property
    def relationship_category(self) -> RelationshipCategory:
        if self.member_relationship in SPOUSE_LIKE:
            return RelationshipCategory.spouse
        if self.member_relationship in CHILD_LIKE:
            return RelationshipCategory.child
        raise ValueError(f"Unsupported member_relationship: {self.member_relationship}")


class Member(BaseModel):
    id: str
    first_name: str
    last_name: str
    dob: date
    employer: str
    hire_date: date
    state: str = Field(min_length=2, max_length=2)
    zip_code: str
    dependents: list[Dependent] = Field(default_factory=list)
    enrolled_plan: str | None = None  # plan id; None = waived coverage

    @property
    def spouse(self) -> Dependent | None:
        return next((d for d in self.dependents
                     if d.relationship_category == RelationshipCategory.spouse), None)

    @property
    def children(self) -> list[Dependent]:
        return [d for d in self.dependents
                if d.relationship_category == RelationshipCategory.child]

    @property
    def coverage_type(self) -> CoverageType:
        has_spouse = self.spouse is not None
        n_kids = len(self.children)
        if has_spouse and n_kids:
            return CoverageType.member_family
        if has_spouse:
            return CoverageType.member_spouse
        if n_kids == 1:
            return CoverageType.member_child
        if n_kids > 1:
            return CoverageType.member_children
        return CoverageType.member


class Plan(BaseModel):
    id: str
    plan_name: str
    carrier: str
    state: str = Field(min_length=2, max_length=2)
    line_of_coverage: str = "medical"
    premium_type: str = "age_banded"  # Clasp: "age_banded" | "composite"
    metal_level: str | None = None
    deductible: Decimal | None = None
    oop_max: Decimal | None = None
    base_rate_21: Decimal = Field(gt=0, description="Monthly premium for a 21-year-old")


class ContributionType(str, Enum):
    """Subset of Clasp's ContributionTypeEnum implemented so far."""

    employer_percentage = "employer_percentage"  # % of this member's premium
    flat_employer_cost = "flat_employer_cost"    # flat $ per month


class ContributionRule(BaseModel):
    contribution_type: ContributionType
    contribution: Decimal = Field(ge=0)
    monthly_max_threshold: Decimal | None = None


class ContributionStrategy(BaseModel):
    """Clasp `benefit_split` strategy: one rule per coverage_type."""

    strategy_type: str = "benefit_split"
    employer_contribution: dict[CoverageType, ContributionRule]


class Group(BaseModel):
    id: str
    name: str
    state: str = Field(min_length=2, max_length=2)
    plan_year_start: date
    members: list[Member]
    plans: list[Plan]

    def plan(self, plan_id: str) -> Plan:
        for p in self.plans:
            if p.id == plan_id:
                return p
        raise KeyError(plan_id)

    @property
    def enrolled_members(self) -> list[Member]:
        return [m for m in self.members if m.enrolled_plan is not None]
