import type { Option } from "@/lib/api";
import { money, signedMoney, signedPct } from "@/lib/api";

function missText(o: Option) {
  const parts: string[] = [];
  if (o.violations.employer_increase_pct !== undefined) parts.push(`over budget by ${o.violations.employer_increase_pct.toFixed(1)} pts`);
  if (o.violations.employee_monthly_increase !== undefined) parts.push(`over the employee cap by ${money(o.violations.employee_monthly_increase, true)}/mo`);
  return parts.join(" and ");
}

export function OptionCard({ o, total, selected, onSelect }:
  { o: Option; total: number; selected: boolean; onSelect: () => void }) {
  const dark = o.feasible && o.rank === 1;
  const ink = dark ? "text-white" : "text-ink";
  const muted = dark ? "text-[#C8DCCF]" : "text-ink-2";
  const note = o.feasible
    ? (o.moved_to_higher_deductible > 0 && o.target_deductible !== null
        ? `Tradeoff: ${o.moved_to_higher_deductible} of ${total} employees move to a ${money(o.target_deductible)} deductible.`
        : "No one moves to a higher deductible.")
    : `Closest miss for this design: ${missText(o)}.`;

  return (
    <article
      className={`flex flex-col gap-4 rounded-[20px] border p-[22px] transition-shadow ${
        dark ? "border-deep bg-deep" : "border-line bg-surface"} ${selected ? "ring-2 ring-green ring-offset-2 ring-offset-ground" : ""}`}>
      <div className="flex items-center justify-between">
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${o.feasible ? "bg-mint text-deep" : "bg-amber-soft text-amber"}`}>
          {o.feasible ? "Meets all goals" : "Misses goals"}
        </span>
        <span className={`num text-xs ${muted}`}>Option {o.rank}</span>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className={`m-0 text-lg font-semibold ${ink}`}>{o.design}</h3>
        <span className={`text-[13px] ${muted}`}>Employer pays {o.employee_only_pct}% employee-only · {o.dependent_pct}% with dependents</span>
      </div>
      <div className="flex flex-col gap-0.5">
        <span className={`num text-3xl font-medium tracking-tight ${ink}`}>{money(o.employer_annual)}</span>
        <span className={`num text-[13px] ${muted}`}>per year · {signedPct(o.employer_change_pct)} vs today</span>
      </div>
      <dl className={`m-0 grid grid-cols-2 gap-3 border-t pt-3.5 ${dark ? "border-[#35604A]" : "border-line"}`}>
        <div className="flex flex-col gap-0.5">
          <dt className={`text-xs ${muted}`}>Pay more</dt>
          <dd className={`num m-0 text-base ${ink}`}>{o.employees_paying_more} of {total}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className={`text-xs ${muted}`}>Largest increase</dt>
          <dd className={`num m-0 text-base ${ink}`}>{o.max_employee_increase > 0 ? `${signedMoney(o.max_employee_increase, true)}/mo` : "None"}</dd>
        </div>
      </dl>
      <p className={`m-0 flex-1 text-[13px] leading-normal ${muted}`}>{note}</p>
      <button type="button" onClick={onSelect} aria-pressed={selected}
        className={`min-h-11 rounded-full text-sm font-semibold transition-colors ${
          dark ? "bg-mint text-deep hover:bg-white" : "border border-[#C9D3CC] bg-surface text-ink hover:bg-tint"}`}>
        {selected ? "Showing employee impact" : "See employee impact"}
      </button>
    </article>
  );
}
