"use client";

import { useState } from "react";
import type { Filings } from "@/lib/api";
import { pct } from "@/lib/api";

// One dot per carrier's average requested 2027 increase, the reference line
// (market median or chosen carrier's average), the chosen carrier's product
// range as a band, and this group's aging-free rate change. Hover, focus or
// tap a dot to see that carrier's filing.
export function BenchmarkStrip({ filings, groupPct, referencePct, referenceLabel, band, highlight }: {
  filings: Filings; groupPct?: number; referencePct: number; referenceLabel: string;
  band?: [number, number]; highlight?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const W = 700, H = 156, L = 24, R = 676;
  const max = Math.max(30, Math.ceil(Math.max(filings.high_pct, groupPct ?? 0, band?.[1] ?? 0) / 5) * 5);
  const x = (p: number) => L + (Math.max(0, p) / max) * (R - L);
  // Simple beeswarm: put each dot in the first row (centre, above, below, ...) where it
  // doesn't overlap a dot already placed, so every carrier stays visible and hoverable.
  const rows = [0, -1, 1, -2, 2, -3, 3];
  const rowOf = new Map<number, number>();
  const placed: { px: number; row: number }[] = [];
  filings.carriers.map((c, i) => ({ i, px: x(c.requested_pct) })).sort((a, b) => a.px - b.px)
    .forEach(({ i, px }) => {
      const row = rows.find((r) => !placed.some((d) => d.row === r && Math.abs(d.px - px) < 15)) ?? 0;
      placed.push({ px, row }); rowOf.set(i, row);
    });
  const cyOf = (i: number) => 90 + (rowOf.get(i) ?? 0) * 13;
  const ticks = Array.from({ length: max / 5 + 1 }, (_, i) => i * 5);
  const labelAnchor = (px: number) => (px < 90 ? "start" : px > W - 90 ? "end" : "middle");
  const gx = groupPct === undefined ? null : x(groupPct), rx = x(referencePct);
  const tip = active === null ? null : filings.carriers[active];

  return (
    <figure className="m-0 flex flex-col gap-2.5">
      <div className="relative" onPointerLeave={(e) => { if (e.pointerType === "mouse") setActive(null); }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="group"
          aria-label={`Requested 2027 rate changes for ${filings.carriers.length} Pennsylvania carriers, ${pct(filings.low_pct)} to ${pct(filings.high_pct)}; ${referenceLabel} ${pct(referencePct)}${groupPct === undefined ? "" : `; this renewal ${pct(groupPct)}`}.`}>
          {band && <rect x={x(band[0])} y={70} width={Math.max(2, x(band[1]) - x(band[0]))} height={40} rx={8} fill="#EAF3EC" />}
          <line x1={L} y1={90} x2={R} y2={90} stroke="#E3E7E1" strokeWidth={2} />
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} y1={86} x2={x(t)} y2={94} stroke="#C9D3CC" strokeWidth={1.5} />
              <text x={x(t)} y={122} textAnchor="middle" fontSize={12} fill="#5E6B63" fontFamily="IBM Plex Mono, monospace">{t}%</text>
            </g>
          ))}
          <line x1={rx} y1={40} x2={rx} y2={104} stroke="#4A5A50" strokeWidth={1.5} strokeDasharray="4 4" />
          <text x={rx} y={30} textAnchor={labelAnchor(rx)} fontSize={12} fill="#4A5A50">{referenceLabel} {pct(referencePct)}</text>
          {gx !== null && groupPct !== undefined && (
            <>
              <circle cx={gx} cy={90} r={10} fill="#1F3D2C" stroke="#FFFFFF" strokeWidth={3} />
              <text x={gx} y={146} textAnchor={labelAnchor(gx)} fontSize={13} fontWeight={600} fill="#16241C">This renewal {pct(groupPct)}</text>
            </>
          )}
          {filings.carriers.map((c, i) => {
            const on = c.company === highlight, hot = i === active;
            return (
              <g key={c.company} tabIndex={0} role="button" className="cursor-pointer outline-none"
                aria-label={`${c.company}: ${pct(c.requested_pct, 2)} requested`}
                onPointerEnter={(e) => { if (e.pointerType === "mouse") setActive(i); }}
                onFocus={() => setActive(i)}
                onClick={() => setActive(i)}>
                <circle cx={x(c.requested_pct)} cy={cyOf(i)} r={8} fill="transparent" />
                <circle cx={x(c.requested_pct)} cy={cyOf(i)} r={hot ? 8 : on ? 7 : 6}
                  fill={hot || on ? "#2D553E" : "#9DB3A5"} stroke="#FFFFFF" strokeWidth={2} />
              </g>
            );
          })}
        </svg>
        {tip && active !== null && (() => {
          const left = (x(tip.requested_pct) / W) * 100, right = left > 60;
          return (
            <div role="tooltip"
              className="pointer-events-none absolute z-10 hidden w-64 -translate-y-1/2 rounded-xl sm:block border border-line bg-surface px-3.5 py-3 text-xs shadow-lg"
              style={{
                top: `${(cyOf(active) / H) * 100}%`,
                ...(right ? { right: `calc(${100 - left}% + 14px)` } : { left: `calc(${left}% + 14px)` }),
              }}>
              <p className="m-0 text-[13px] font-semibold leading-snug text-ink">{tip.company}</p>
              <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-ink-2">
                <dt>Requested</dt><dd className="num m-0 text-right font-medium text-ink">{pct(tip.requested_pct, 2)}</dd>
                <dt>Product range</dt><dd className="num m-0 whitespace-nowrap text-right">{tip.range_low_pct === tip.range_high_pct ? pct(tip.range_low_pct, 1) : `${pct(tip.range_low_pct, 1)} to ${pct(tip.range_high_pct, 1)}`}</dd>
                {groupPct !== undefined && (
                  <><dt>This renewal</dt><dd className="num m-0 text-right">
                    {Math.abs(groupPct - tip.requested_pct) < 0.05 ? "about the same"
                      : `${Math.abs(groupPct - tip.requested_pct).toFixed(1)} pts ${groupPct > tip.requested_pct ? "higher" : "lower"}`}
                  </dd></>
                )}
              </dl>
            </div>
          );
        })()}
      </div>
      {tip && (
        <div className="rounded-xl border border-line bg-surface px-3.5 py-3 text-xs sm:hidden" aria-live="polite">
          <p className="m-0 text-[13px] font-semibold text-ink">{tip.company}</p>
          <p className="num m-0 mt-1 text-ink-2">
            {pct(tip.requested_pct, 2)} requested · products {pct(tip.range_low_pct, 1)} to {pct(tip.range_high_pct, 1)}
          </p>
        </div>
      )}
      <figcaption className="text-xs leading-relaxed text-ink-3">
        Each dot is one carrier&apos;s average requested increase for 1/1/2027{band ? "; the shaded band is the selected carrier's product range" : ""}.
        Hover or tap a dot for details. Source: ratereview.healthcare.gov, retrieved {filings.retrieved}. Requested rates, not final;
        regulators often approve less.
      </figcaption>
    </figure>
  );
}
