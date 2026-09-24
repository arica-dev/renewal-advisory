"use client";

import { useState } from "react";
import type { EmployeeRow } from "@/lib/api";
import { money, signedMoney } from "@/lib/api";

export function EmployeeTable({ rows, title }: { rows: EmployeeRow[]; title: string }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, 8);
  const more = rows.filter((r) => r.change > 0.005).length;
  const less = rows.filter((r) => r.change < -0.005).length;

  return (
    <section aria-label="Effect on each employee" className="overflow-hidden rounded-[20px] border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-5">
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-lg font-semibold">Effect on each employee · {title}</h2>
          <span className="text-[13px] text-ink-3">Monthly premium share. {more} pay more, {less} pay less. Sorted by change.</span>
        </div>
        {rows.length > 8 && (
          <button type="button" onClick={() => setAll((v) => !v)} className="min-h-11 text-sm font-semibold text-green hover:text-deep">
            {all ? "Show fewer" : `View all ${rows.length}`}
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-ink-3">
              <th scope="col" className="px-6 py-3 font-semibold">Employee</th>
              <th scope="col" className="px-4 py-3 font-semibold">Coverage</th>
              <th scope="col" className="px-4 py-3 font-semibold">Plan</th>
              <th scope="col" className="px-4 py-3 text-right font-semibold">Today</th>
              <th scope="col" className="px-4 py-3 text-right font-semibold">At renewal</th>
              <th scope="col" className="px-6 py-3 text-right font-semibold">Change</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id} className="border-b border-line-2 last:border-b-0">
                <td className="px-6 py-3.5 font-medium">{r.name}</td>
                <td className="px-4 py-3.5 text-ink-2">{r.coverage}</td>
                <td className="px-4 py-3.5 text-ink-2">
                  {r.plan_today === r.plan_renewal ? r.plan_today : <>{r.plan_today} <span aria-label="to">→</span> {r.plan_renewal}</>}
                </td>
                <td className="num px-4 py-3.5 text-right">{money(r.pays_today, true)}</td>
                <td className="num px-4 py-3.5 text-right">{money(r.pays_renewal, true)}</td>
                <td className={`num px-6 py-3.5 text-right font-medium ${r.change > 0.005 ? "text-amber" : "text-green"}`}>
                  {Math.abs(r.change) < 0.005 ? "$0.00" : signedMoney(r.change, true)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
