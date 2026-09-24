"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, type Analysis, type Filings, type Goals, longDate, money, pct, signedMoney, signedPct } from "@/lib/api";
import { BenchmarkStrip } from "@/components/BenchmarkStrip";
import { EmployeeTable } from "@/components/EmployeeTable";
import { GoalsPanel } from "@/components/GoalsPanel";
import { Icon } from "@/components/Icon";
import { OptionCard } from "@/components/OptionCard";
import { Breadcrumbs, Card, ErrorState, Pill, Skeleton, VerdictPill, btn, field } from "@/components/ui";

const DEFAULT_GOALS: Goals = {
  max_employer_increase_pct: 5, max_employee_monthly_increase: 100, min_employee_only_pct: 50,
  max_deductible: null, objective: "protect_employees", employee_only_pct: 70, dependent_pct: 70,
};
const MARKET = "market";

export default function GroupPage() {
  const { id } = useParams<{ id: string }>();
  const [goals, setGoals] = useState<Goals>(DEFAULT_GOALS);
  const [compareTo, setCompareTo] = useState(MARKET);
  const [data, setData] = useState<Analysis | null>(null);
  const [filings, setFilings] = useState<Filings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<number | "accept">(1);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    api.filings(ctl.signal).then(setFilings).catch(() => { /* strip just won't render */ });
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    setLoading(true);
    setError(null);
    api.analysis(id, { ...goals, max_deductible: goals.max_deductible, compare_to: compareTo }, ctl.signal)
      .then((a) => { setData(a); setSelected(a.options.length ? 1 : "accept"); })
      .catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); })
      .finally(() => { if (!ctl.signal.aborted) setLoading(false); });
    return () => ctl.abort();
  }, [id, goals, compareTo, attempt]);

  const table = useMemo(() => {
    if (!data) return null;
    if (selected === "accept") return { rows: data.accept_renewal.employees, title: "Accept renewal as is" };
    const o = data.options.find((x) => x.rank === selected) ?? data.options[0];
    return o ? { rows: o.employees, title: `Option ${o.rank}` } : { rows: data.accept_renewal.employees, title: "Accept renewal as is" };
  }, [data, selected]);

  if (error) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (!data) return <PageSkeleton />;

  const { group: g, breakdown: b, benchmark: bm } = data;
  const briefHref = `/groups/${g.id}/brief${compareTo !== MARKET ? `?compare_to=${encodeURIComponent(compareTo)}` : ""}`;
  const refLabel = bm.compare_to === MARKET ? "PA median" : "Carrier average";
  const headline = bm.verdict === "above_range"
    ? `The rate change is above every product in ${bm.against}'s filing.`
    : bm.verdict === "above_average"
      ? `The rate change is ${bm.gap_pct.toFixed(1)} points above ${bm.compare_to === MARKET ? "the Pennsylvania market median" : `${bm.against}'s filed average`}.`
      : `The rate change is in line with ${bm.compare_to === MARKET ? "the Pennsylvania market" : `${bm.against}'s filing`}.`;
  const shares = [b.current_monthly, b.aging, b.rate].map((v) => (v / b.renewal_monthly) * 100);

  return (
    <div className={`flex flex-col gap-6 transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
      <header className="flex flex-col gap-3.5">
        <Breadcrumbs items={[{ label: "Renewals", href: "/" }, { label: g.name }]} />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-2.5">
            <h1 className="m-0 text-[34px] font-semibold tracking-tight">{g.name}</h1>
            <div className="flex flex-wrap gap-2">
              <Pill tone="outline" className="font-normal">{g.enrolled} enrolled of {g.size}</Pill>
              <Pill tone="outline" className="font-normal">{g.carrier} · {data.plans.map((p) => p.name.split(" ")[0]).join(", ")}</Pill>
              <Pill tone="outline" className="font-normal">Renews {longDate(g.renewal_date)} · {g.days_to_renewal} days</Pill>
            </div>
          </div>
          <div className="flex gap-2.5">
            <button type="button" className={btn.secondary} onClick={() => window.print()}>Print summary</button>
            <Link href={briefHref} className={btn.primary}>Draft push-back brief <Icon name="arrow" size={16} className="text-mint" /></Link>
          </div>
        </div>
      </header>

      <Card className="flex flex-col gap-5 p-6" aria-label="What's driving the increase">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="m-0 text-lg font-semibold">What&apos;s driving the increase</h2>
          <span className="text-[13px] text-ink-3">Monthly premium, all enrolled employees and dependents</span>
        </div>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Today" value={money(b.current_monthly)} note="per month" />
          <Stat label="At renewal" value={money(b.renewal_monthly)} note={signedPct(b.total_pct)} noteClass="text-amber font-medium" />
          <Stat label="From employees aging" value={signedMoney(b.aging)} note={`${b.aging_pct.toFixed(1)} pts of the increase`} />
          <Stat label="From the rate change" value={signedMoney(b.rate)} note={`${b.rate_pct.toFixed(1)} pts of the increase`} />
        </div>
        <div className="flex flex-col gap-2">
          <div role="img" aria-label={`Renewal premium: ${shares[0]!.toFixed(1)}% today's premium, ${shares[1]!.toFixed(1)}% aging, ${shares[2]!.toFixed(1)}% rate change`}
            className="flex h-3.5 gap-0.5 overflow-hidden rounded-full">
            <div style={{ width: `${shares[0]}%` }} className="bg-[#CFD8D1]" />
            <div style={{ width: `${shares[1]}%` }} className="bg-[#7FA88E]" />
            <div style={{ width: `${shares[2]}%` }} className="bg-deep" />
          </div>
          <div className="flex flex-wrap gap-5 text-xs text-ink-2">
            <Legend color="bg-[#CFD8D1]" label="Today's premium" />
            <Legend color="bg-[#7FA88E]" label="Aging" />
            <Legend color="bg-deep" label="Rate change" />
          </div>
        </div>
      </Card>

      <Card className="grid items-center gap-8 p-6 lg:grid-cols-[340px_minmax(0,1fr)]" aria-label="Benchmark against 2027 filings">
        <div className="flex flex-col gap-3">
          <div><VerdictPill verdict={bm.verdict} /></div>
          <h2 className="m-0 text-[22px] font-semibold leading-tight tracking-tight">{headline}</h2>
          <p className="m-0 text-sm leading-relaxed text-ink-2">
            With aging removed, this renewal raises rates <b className="num text-ink">{pct(bm.group_rate_pct)}</b>.{" "}
            {bm.compare_to === MARKET
              ? <>Pennsylvania small-group carriers {bm.requested ? "requested" : "were approved for"} a median <b className="num text-ink">{pct(bm.reference_pct)}</b> for 2027.</>
              : <>{bm.against} {bm.requested ? "requested" : "was approved for"} <b className="num text-ink">{pct(bm.reference_pct)}</b> on average, with products from <span className="num">{pct(bm.range_low_pct)}</span> to <span className="num">{pct(bm.range_high_pct)}</span>.</>}
          </p>
          <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Compare with
            <select className={field} value={compareTo} onChange={(e) => setCompareTo(e.target.value)}>
              <option value={MARKET}>PA small-group market ({filings?.carriers.length ?? 16} carriers)</option>
              {filings?.carriers.map((c) => c.company).sort().map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        </div>
        {filings ? (
          <BenchmarkStrip filings={filings} groupPct={bm.group_rate_pct} referencePct={bm.reference_pct}
            referenceLabel={refLabel} highlight={bm.compare_to === MARKET ? undefined : bm.against}
            band={bm.compare_to === MARKET ? undefined : [bm.range_low_pct, bm.range_high_pct]} />
        ) : <Skeleton className="h-[180px]" />}
      </Card>

      <section aria-label="Options for the employer" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="m-0 text-lg font-semibold">Options for the employer</h2>
            <span className="text-[13px] text-ink-3">
              Searched {data.search.evaluated.toLocaleString()} combinations of plan design and contribution.
              {" "}Accepting as is: {money(data.accept_renewal.employer_annual)}/yr ({signedPct(data.accept_renewal.employer_change_pct)}).
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <GoalChip>Employer ≤ {signedPct(goals.max_employer_increase_pct)}</GoalChip>
            <GoalChip>No employee &gt; +{money(goals.max_employee_monthly_increase)}/mo</GoalChip>
            <GoalChip>Employer pays ≥ {goals.min_employee_only_pct}%</GoalChip>
            {goals.max_deductible !== null && <GoalChip>Deductible ≤ {money(goals.max_deductible)}</GoalChip>}
            <button type="button" className={`${btn.chip} border-[#C9D3CC] bg-surface font-semibold text-ink hover:bg-tint`}
              aria-expanded={editing} onClick={() => setEditing((v) => !v)}>
              <Icon name="sliders" size={15} className="mr-1.5" /> Edit goals
            </button>
          </div>
        </div>
        {editing && <GoalsPanel goals={goals} onClose={() => setEditing(false)}
          onApply={(n) => { setGoals(n); setEditing(false); }} />}
        {!data.search.any_feasible && (
          <div role="status" className="flex items-start gap-3 rounded-2xl border border-[#F3D9B1] bg-amber-soft px-5 py-4 text-sm text-[#5C3209]">
            <Icon name="info" className="mt-0.5 text-amber" />
            <span><b>No option meets every goal.</b> These are the closest misses. Negotiating the rate toward the benchmark, or relaxing a goal, opens up options.</span>
          </div>
        )}
        <div className="grid gap-4 lg:grid-cols-3">
          {data.options.map((o) => (
            <OptionCard key={o.rank} o={o} total={g.enrolled} selected={selected === o.rank} onSelect={() => setSelected(o.rank)} />
          ))}
        </div>
        <button type="button" onClick={() => setSelected("accept")} aria-pressed={selected === "accept"}
          className="self-start text-sm font-semibold text-green hover:text-deep">
          {selected === "accept" ? "Showing: accept renewal as is" : "Compare with accepting the renewal as is"}
        </button>
      </section>

      {table && <EmployeeTable rows={table.rows} title={table.title} />}
    </div>
  );
}

function Stat({ label, value, note, noteClass = "text-ink-3" }: { label: string; value: string; note: string; noteClass?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] text-ink-2">{label}</span>
      <span className="num text-[30px] font-medium tracking-tight">{value}</span>
      <span className={`num text-xs ${noteClass}`}>{note}</span>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1.5"><span className={`size-2.5 rounded-[3px] ${color}`} />{label}</span>;
}

function GoalChip({ children }: { children: React.ReactNode }) {
  return <span className="num rounded-full bg-mint-soft px-2.5 py-1.5 text-xs text-deep">{children}</span>;
}

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-10 w-80" />
      <Skeleton className="h-[220px] rounded-[20px]" />
      <Skeleton className="h-[260px] rounded-[20px]" />
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[380px] rounded-[20px]" />)}
      </div>
    </div>
  );
}
