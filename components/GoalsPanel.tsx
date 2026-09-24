"use client";

import { useState } from "react";
import type { Goals } from "@/lib/api";
import { btn, field } from "./ui";

export function GoalsPanel({ goals, onApply, onClose }:
  { goals: Goals; onApply: (g: Goals) => void; onClose: () => void }) {
  const [d, setD] = useState<Goals>(goals);
  const num = (k: keyof Goals) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setD((g) => ({ ...g, [k]: e.target.value === "" ? 0 : Number(e.target.value) }));

  return (
    <form
      aria-label="Edit goals"
      onSubmit={(e) => { e.preventDefault(); onApply(d); }}
      className="grid gap-4 rounded-[20px] border border-line bg-surface p-5 md:grid-cols-4">
      <fieldset className="m-0 grid gap-3 border-0 p-0 md:col-span-2 md:grid-cols-2">
        <legend className="mb-1 text-[13px] font-semibold text-green">The employer's goals</legend>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Max employer increase (%)
          <input type="number" step="0.5" className={field} value={d.max_employer_increase_pct} onChange={num("max_employer_increase_pct")} />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Max increase for any employee ($/mo)
          <input type="number" step="5" min="0" className={field} value={d.max_employee_monthly_increase} onChange={num("max_employee_monthly_increase")} />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Highest deductible allowed
          <select className={field} value={d.max_deductible ?? ""}
            onChange={(e) => setD((g) => ({ ...g, max_deductible: e.target.value === "" ? null : Number(e.target.value) }))}>
            <option value="">Any</option>
            <option value="1500">$1,500</option>
            <option value="3500">$3,500</option>
            <option value="6000">$6,000</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Carrier minimum, employee-only (%)
          <input type="number" step="5" min="0" max="100" className={field} value={d.min_employee_only_pct} onChange={num("min_employee_only_pct")} />
        </label>
      </fieldset>
      <fieldset className="m-0 grid gap-3 border-0 p-0">
        <legend className="mb-1 text-[13px] font-semibold text-green">Today's contribution</legend>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Employee-only (%)
          <input type="number" step="5" min="0" max="100" className={field} value={d.employee_only_pct} onChange={num("employee_only_pct")} />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">With dependents (%)
          <input type="number" step="5" min="0" max="100" className={field} value={d.dependent_pct} onChange={num("dependent_pct")} />
        </label>
      </fieldset>
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-1 text-[13px] font-semibold text-green">Within the goals, prefer</legend>
        {([["protect_employees", "Lowest cost to employees"], ["lowest_employer_cost", "Lowest cost to employer"]] as const).map(([v, label]) => (
          <label key={v} className="flex min-h-11 items-center gap-2.5 rounded-xl border border-field px-3 text-sm">
            <input type="radio" name="objective" value={v} checked={d.objective === v}
              onChange={() => setD((g) => ({ ...g, objective: v }))} className="size-4 accent-green" />
            {label}
          </label>
        ))}
        <div className="mt-auto flex gap-2 pt-2">
          <button type="submit" className={`${btn.primary} flex-1`}>Apply</button>
          <button type="button" className={btn.secondary} onClick={onClose}>Cancel</button>
        </div>
      </fieldset>
    </form>
  );
}
