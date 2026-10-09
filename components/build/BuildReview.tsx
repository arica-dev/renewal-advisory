"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { signedPct } from "@/lib/api";
import {
  ApiError, buildApi, shortDate, usd, usd0,
  type BuildOutput, type Check, type Contribution, type Extraction, type OpenEnrollment, type Packet, type Rate,
} from "@/lib/build";
import { Icon } from "@/components/Icon";
import { Card, Pill, btn, field } from "@/components/ui";
import { SourceViewer } from "./SourceViewer";
import { RequestList } from "./RequestList";

const STATUS_LABEL: Record<string, string> = {
  renews: "Renews", renamed: "Renamed", replaced: "Replaced", modified: "Benefits change",
  discontinued: "Discontinued", new: "New plan",
};

function firstAge(label: string) {
  const m = label.match(/^\d+/);
  return m ? Number(m[0]) : 999;
}

/** Apply the fixes a person accepted to the packet as extracted. Recomputed from
 *  the original each time, so undoing a fix is just removing it from the set. */
function applyFixes(original: Packet, checks: Check[], applied: Set<string>): Packet {
  const p: Packet = structuredClone(original);
  for (const c of checks) {
    if (!applied.has(c.id) || !c.fix) continue;
    const plan = p.plans.find((x) => x.key === c.plan);
    if (c.fix.action === "set_rate" && plan) {
      const r = plan.rates.find((x) => x.label === c.fix!.label);
      if (r) { r.amount = c.fix.amount!; r.source = { ...r.source, edited: true }; }
    } else if (c.fix.action === "add_rate" && plan) {
      plan.rates.push({ label: c.fix.label!, amount: c.fix.amount!, source: { edited: true } });
      plan.rates.sort((a, b) => firstAge(a.label) - firstAge(b.label));
    } else if (c.fix.action === "set_effective_date") {
      p.effective_date = c.fix.value!;
    }
  }
  return p;
}

function actionsFor(c: Check): { fix?: string; keep?: string } {
  const amount = c.fix?.amount ? usd(c.fix.amount) : "";
  switch (c.kind) {
    case "age_curve": return { fix: `Use ${amount}`, keep: "Keep as printed" };
    case "missing_age": return { fix: `Add ${amount}` };
    case "effective_date": return { fix: "Use Clasp's date", keep: "Keep the packet's date" };
    case "mapping": return { keep: "Confirm mapping" };
    case "unverified": return { keep: "I checked the document" };
    case "plan_missing": case "discontinued": return { keep: "Plan ends, keep going" };
    default: return c.severity === "info" ? {} : { keep: "Acknowledge" };
  }
}

export function BuildReview({ result, actions }: { result: Extraction; actions?: React.ReactNode }) {
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [kept, setKept] = useState<Set<string>>(new Set());
  const [activeKey, setActiveKey] = useState(result.packet.plans[0]?.key ?? "");
  const [selected, setSelected] = useState<string | null>(null);
  const [oe, setOe] = useState<OpenEnrollment>(result.open_enrollment);
  const [contribution, setContribution] = useState<Contribution>({
    employee_only_pct: result.context?.contribution?.employee_only_pct ?? "70.00",
    dependent_pct: result.context?.contribution?.dependent_pct ?? "70.00",
  });
  const [output, setOutput] = useState<BuildOutput | null>(null);
  const [busy, setBusy] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  const packet = useMemo(() => applyFixes(result.packet, result.checks, applied), [result, applied]);
  const ctx = result.context;
  const actionable = result.checks.filter((c) => c.severity !== "info");
  const info = result.checks.filter((c) => c.severity === "info");
  const state = (c: Check) => (applied.has(c.id) ? "fixed" : kept.has(c.id) ? "kept" : "open");
  const open = actionable.filter((c) => state(c) === "open");
  const flaggedLabels = new Map(result.checks.filter((c) => c.plan && c.label).map((c) => [`${c.plan}:${c.label}`, c]));

  const activePlan = packet.plans.find((p) => p.key === activeKey) ?? packet.plans[0];
  const selectedRate: Rate | null = activePlan?.rates.find((r) => `${activePlan.key}:${r.label}` === selected) ?? null;
  const fallbackPage = activePlan?.rates[0]?.source?.page ?? 1;
  const fallbackSheet = activePlan?.rates.find((r) => r.source?.sheet)?.source?.sheet;

  function touch() { setOutput(null); setGenError(null); }
  function toggle(set: Set<string>, id: string, on: boolean, setter: (s: Set<string>) => void) {
    const next = new Set(set);
    if (on) next.add(id); else next.delete(id);
    setter(next);
    touch();
  }
  function focus(c: Check) {
    if (c.plan && c.label) { setActiveKey(c.plan); setSelected(`${c.plan}:${c.label}`); }
    else if (c.plan && packet.plans.some((p) => p.key === c.plan)) setActiveKey(c.plan);
  }

  async function generate() {
    setBusy(true);
    setGenError(null);
    try {
      setOutput(await buildApi.generate(packet, [...kept], oe, contribution));
    } catch (e) {
      const err = e as ApiError;
      const unresolved = (err.data as { unresolved?: Check[] } | null)?.unresolved;
      setGenError(unresolved ? `${err.message} ${unresolved.map((u) => u.title).join("; ")}.` : err.message);
    } finally {
      setBusy(false);
    }
  }

  const clasp = (id?: string) => ctx?.plans.find((p) => p.id === id);
  const rate21 = (rates: Rate[]) => rates.find((r) => r.label === "21")?.amount;
  const extractedBy = result.extractor.method === "claude"
    ? `Claude (${result.extractor.model})${result.extractor.cached ? ", cached" : ""}` : "the built-in parser";

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <p className="m-0 text-[13px] font-medium text-ink-2">
            {packet.carrier ?? "Carrier"} renewal · read from {result.filename} by {extractedBy}
          </p>
          <h1 className="m-0 text-[30px] font-semibold tracking-tight">{ctx?.employer_name ?? packet.employer_name ?? "Renewal packet"}</h1>
          <p className="m-0 text-sm text-ink-2">
            Effective {shortDate(packet.effective_date)} · {packet.plans.length} plans
            {ctx && <> · {ctx.enrolled} enrolled in Clasp</>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {actions}
          <Pill tone={open.length ? "amber" : "green"} className="text-[13px]">
            {open.length ? `${open.length} to resolve before building` : "Ready to build"}
          </Pill>
        </div>
      </header>
      {result.extractor.fallback && (
        <p role="status" className="m-0 rounded-xl bg-amber-soft px-4 py-2.5 text-[13px] text-amber">{result.extractor.fallback}</p>
      )}

      {/* 1. Resolve */}
      <Card className="flex flex-col gap-4 p-5 md:p-6" aria-labelledby="resolve">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="resolve" className="m-0 text-lg font-semibold">1 · Resolve</h2>
          <span className="text-[13px] text-ink-3">{actionable.length - open.length} of {actionable.length} done</span>
        </div>
        {actionable.length === 0 && <p className="m-0 text-sm text-ink-2">Nothing to resolve. Every value was found and fits the checks.</p>}
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {actionable.map((c) => {
            const s = state(c);
            const a = actionsFor(c);
            return (
              <li key={c.id} className={`flex flex-col gap-3 rounded-xl border px-4 py-3 md:flex-row md:items-center ${s === "open" ? (c.severity === "blocker" ? "border-amber/40 bg-amber-soft/60" : "border-line bg-ground") : "border-line bg-surface"}`}>
                <button type="button" onClick={() => focus(c)} className="flex flex-1 flex-col gap-1 text-left">
                  <span className="flex flex-wrap items-center gap-2">
                    {s === "open"
                      ? <Pill tone={c.severity === "blocker" ? "amber" : "outline"}>{c.severity === "blocker" ? "Must fix" : "Confirm"}</Pill>
                      : <Pill tone="green"><Icon name="check" size={13} /> {s === "fixed" ? "Fixed" : c.kind === "mapping" ? "Confirmed" : "Kept"}</Pill>}
                    <span className="text-[15px] font-semibold">{c.title}</span>
                  </span>
                  <span className="text-[13px] leading-relaxed text-ink-2">{c.detail}</span>
                </button>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {s === "open" ? (
                    <>
                      {a.fix && c.fix && <button type="button" className={btn.primary} onClick={() => { toggle(applied, c.id, true, setApplied); focus(c); }}>{a.fix}</button>}
                      {a.keep && c.can_keep && <button type="button" className={btn.secondary} onClick={() => toggle(kept, c.id, true, setKept)}>{a.keep}</button>}
                    </>
                  ) : (
                    <button type="button" className="text-[13px] font-medium text-green underline-offset-2 hover:underline"
                      onClick={() => { toggle(applied, c.id, false, setApplied); toggle(kept, c.id, false, setKept); }}>Undo</button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* 2. Plans */}
      <Card className="overflow-hidden" aria-labelledby="plans">
        <div className="border-b border-line px-5 py-4 md:px-6">
          <h2 id="plans" className="m-0 text-lg font-semibold">2 · Plans</h2>
          <p className="m-0 mt-1 text-[13px] text-ink-2">How each plan in Clasp today carries into the new plan year.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wider text-ink-3">
                <th className="px-5 py-3 md:px-6">In Clasp today</th><th className="py-3" aria-label="maps to" />
                <th className="py-3">Renewal plan</th><th className="py-3">Change</th>
                <th className="py-3 text-right">Age-21 rate</th><th className="px-5 py-3 text-right md:px-6">Increase</th>
              </tr>
            </thead>
            <tbody>
              {packet.plans.map((p) => {
                const cp = clasp(p.clasp_plan_id) ?? ctx?.plans.find((x) => x.plan_name === p.current_plan_name);
                const now = cp?.base_rate_21 ?? p.current_rate_21;
                const next = rate21(p.rates);
                const change = now && next ? (Number(next) / Number(now) - 1) * 100 : null;
                return (
                  <tr key={p.key} className="border-t border-line-2">
                    <td className="px-5 py-3.5 md:px-6">
                      <span className="block font-semibold">{cp?.plan_name ?? p.current_plan_name}</span>
                      <span className="text-xs text-ink-3">{cp ? `${cp.enrolled} enrolled · ${usd0(cp.deductible)} deductible` : "Not in Clasp"}</span>
                    </td>
                    <td className="py-3.5 text-ink-3"><Icon name="arrow" size={16} /></td>
                    <td className="py-3.5">
                      <span className="block font-semibold">{p.renewal_plan_name}</span>
                      <span className="num text-xs text-ink-3">{p.renewal_code}{p.deductible ? ` · ${usd0(p.deductible)} deductible` : ""}</span>
                    </td>
                    <td className="py-3.5"><Pill tone={p.status === "renews" ? "green" : "amber"}>{STATUS_LABEL[p.status] ?? p.status}</Pill></td>
                    <td className="num py-3.5 text-right">{usd(now)} → {usd(next)}</td>
                    <td className="num px-5 py-3.5 text-right font-medium md:px-6">{change === null ? "—" : signedPct(change)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 3. Rates with their source */}
      <Card className="flex flex-col gap-4 p-5 md:p-6" aria-labelledby="rates">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 id="rates" className="m-0 text-lg font-semibold">3 · Rates</h2>
            <p className="m-0 mt-1 text-[13px] text-ink-2">Select any rate to see where it&apos;s printed in the carrier&apos;s document.</p>
          </div>
          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Plan">
            {packet.plans.map((p) => (
              <button key={p.key} type="button" role="tab" aria-selected={p.key === activePlan?.key}
                onClick={() => { setActiveKey(p.key); setSelected(null); }}
                className={`${btn.chip} ${p.key === activePlan?.key ? "border-green bg-mint-soft font-semibold text-deep" : "border-field bg-surface text-ink-2 hover:bg-tint"}`}>
                {p.renewal_plan_name}
              </button>
            ))}
          </div>
        </div>
        {activePlan && (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
            <div className="grid grid-cols-2 content-start gap-1.5 sm:grid-cols-3" role="tabpanel">
              {activePlan.rates.map((r) => {
                const id = `${activePlan.key}:${r.label}`;
                const flag = flaggedLabels.get(id);
                const fixed = r.source?.edited;
                const on = selected === id;
                return (
                  <button key={r.label} type="button" onClick={() => setSelected(id)} aria-pressed={on}
                    className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                      on ? "border-green bg-mint-soft" : fixed ? "border-green/40 bg-mint-soft/50" : flag ? "border-amber/50 bg-amber-soft" : r.source?.verified === false ? "border-amber/50 bg-amber-soft" : "border-line-2 hover:bg-tint"}`}>
                    <span className="text-ink-3">{r.label}</span>
                    <span className="num font-medium">{usd(r.amount)}</span>
                  </button>
                );
              })}
            </div>
            <div className="min-w-0 lg:sticky lg:top-6 lg:self-start">
              <SourceViewer result={result} rate={selectedRate} fallbackPage={fallbackPage} fallbackSheet={fallbackSheet}
                flagged={!!selected && flaggedLabels.has(selected)} />
            </div>
          </div>
        )}
      </Card>

      {/* 4. What it means */}
      {ctx && (output?.preview ?? result.preview) && (() => {
        const pv = (output?.preview ?? result.preview)!;
        return (
          <Card className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between md:p-6" aria-labelledby="impact">
            <div className="flex flex-col gap-1.5">
              <h2 id="impact" className="m-0 text-lg font-semibold">4 · What this renewal means</h2>
              <p className="m-0 max-w-xl text-sm leading-relaxed text-ink-2">
                These rates run through the Renewal Advisor engine: the group&apos;s premium goes
                from <span className="num font-semibold text-ink">{usd0(pv.current_monthly)}</span> to{" "}
                <span className="num font-semibold text-ink">{usd0(pv.renewal_monthly)}</span>/month,{" "}
                <span className="num font-semibold text-ink">{signedPct(pv.total_pct)}</span>. Aging is{" "}
                <span className="num">{pv.aging_pct.toFixed(1)}</span> points of that; the carrier&apos;s rate change is{" "}
                <span className="num">{pv.rate_pct.toFixed(1)}</span>.
              </p>
            </div>
            <Link href={pv.advisor_url} className={btn.secondary}>Open the analysis <Icon name="arrow" size={16} /></Link>
          </Card>
        );
      })()}

      {/* 5. Build */}
      <Card className="flex flex-col gap-5 p-5 md:p-6" aria-labelledby="build">
        <div>
          <h2 id="build" className="m-0 text-lg font-semibold">5 · Build in Clasp</h2>
          <p className="m-0 mt-1 text-[13px] text-ink-2">
            Set the open enrollment window, then generate the API calls. They&apos;re validated against
            Clasp&apos;s request schemas (API version {output?.api_version ?? "2026-04-24"}) before they&apos;re shown.
          </p>
        </div>
        {!ctx ? (
          <p className="m-0 text-sm text-ink-2">This packet doesn&apos;t match a Clasp group, so there&apos;s nothing to build into.</p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-2">Open enrollment starts
                <input type="date" className={field} value={oe.start_date} onChange={(e) => { setOe({ ...oe, start_date: e.target.value }); touch(); }} />
              </label>
              <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-2">Ends
                <input type="date" className={field} value={oe.end_date} onChange={(e) => { setOe({ ...oe, end_date: e.target.value }); touch(); }} />
              </label>
              <label className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-2">Enrollment
                <select className={field} value={oe.enrollment_type}
                  onChange={(e) => { setOe({ ...oe, enrollment_type: e.target.value as OpenEnrollment["enrollment_type"] }); touch(); }}>
                  <option value="passive">Passive: elections carry over</option>
                  <option value="active">Active: everyone re-elects</option>
                </select>
              </label>
            </div>
            <fieldset className="m-0 flex flex-col gap-2 rounded-xl border border-line px-4 py-3">
              <legend className="px-1 text-[13px] font-semibold text-ink">Employer contribution</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {([["employee_only_pct", "Employee-only coverage"], ["dependent_pct", "Coverage with dependents"]] as const).map(([k, label]) => (
                  <label key={k} className="flex flex-col gap-1.5 text-[13px] font-medium text-ink-2">{label}
                    <span className="flex items-center gap-2">
                      <input type="number" min={0} max={100} step={5} className={`${field} num max-w-28`}
                        value={contribution[k] === "" ? "" : Number(contribution[k])}
                        onChange={(e) => { setContribution({ ...contribution, [k]: e.target.value }); touch(); }} />
                      <span className="text-sm text-ink-2">% paid by the employer</span>
                    </span>
                  </label>
                ))}
              </div>
              <p className="m-0 text-xs text-ink-3">
                Carried forward from the group&apos;s current split in Clasp. Change it if the employer chose a
                different split in the Renewal Advisor; payroll deductions follow this.
              </p>
            </fieldset>
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" className={btn.primary} disabled={busy || open.length > 0} onClick={generate}>
                {busy ? "Generating…" : "Generate Clasp requests"}
              </button>
              {open.length > 0 && <span className="text-[13px] text-ink-3">Resolve {open.length} item{open.length > 1 ? "s" : ""} above first.</span>}
            </div>
            {genError && <p role="alert" className="m-0 rounded-xl bg-amber-soft px-3 py-2 text-[13px] text-amber">{genError}</p>}
            {output && <RequestList output={output} name={ctx.group_id} />}
          </>
        )}
      </Card>

      {info.length > 0 && (
        <details className="rounded-2xl border border-line bg-surface px-5 py-4 text-sm md:px-6">
          <summary className="cursor-pointer font-semibold">Market context ({info.length})</summary>
          <ul className="m-0 mt-3 flex list-none flex-col gap-2 p-0">
            {info.map((c) => <li key={c.id} className="text-[13px] text-ink-2"><span className="font-semibold text-ink">{c.title}.</span> {c.detail}</li>)}
          </ul>
        </details>
      )}
    </>
  );
}
