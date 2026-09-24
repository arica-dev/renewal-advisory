import type { Filings } from "@/lib/api";
import { pct } from "@/lib/api";

// One dot per carrier's average requested 2027 increase, the reference line
// (market median or chosen carrier's average), the chosen carrier's product
// range as a band, and this group's aging-free rate change.
export function BenchmarkStrip({ filings, groupPct, referencePct, referenceLabel, band, highlight }: {
  filings: Filings; groupPct?: number; referencePct: number; referenceLabel: string;
  band?: [number, number]; highlight?: string;
}) {
  const W = 700, L = 24, R = 676;
  const max = Math.max(30, Math.ceil(Math.max(filings.high_pct, groupPct ?? 0, band?.[1] ?? 0) / 5) * 5);
  const x = (p: number) => L + (Math.max(0, p) / max) * (R - L);
  const ticks = Array.from({ length: max / 5 + 1 }, (_, i) => i * 5);
  const labelAnchor = (px: number) => (px < 90 ? "start" : px > W - 90 ? "end" : "middle");
  const gx = groupPct === undefined ? null : x(groupPct), rx = x(referencePct);

  return (
    <figure className="m-0 flex flex-col gap-2.5">
      <svg viewBox={`0 0 ${W} 156`} width="100%" role="img"
        aria-label={`Requested 2027 rate changes for ${filings.carriers.length} Pennsylvania carriers, ${pct(filings.low_pct)} to ${pct(filings.high_pct)}; ${referenceLabel} ${pct(referencePct)}${groupPct === undefined ? "" : `; this renewal ${pct(groupPct)}`}.`}>
        {band && <rect x={x(band[0])} y={70} width={Math.max(2, x(band[1]) - x(band[0]))} height={40} rx={8} fill="#EAF3EC" />}
        <line x1={L} y1={90} x2={R} y2={90} stroke="#E3E7E1" strokeWidth={2} />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1={86} x2={x(t)} y2={94} stroke="#C9D3CC" strokeWidth={1.5} />
            <text x={x(t)} y={122} textAnchor="middle" fontSize={12} fill="#5E6B63" fontFamily="IBM Plex Mono, monospace">{t}%</text>
          </g>
        ))}
        {filings.carriers.map((c, i) => {
          const on = c.company === highlight;
          return (
            <circle key={c.company} cx={x(c.requested_pct)} cy={90 - ((i % 3) - 1) * 13} r={on ? 7 : 6}
              fill={on ? "#2D553E" : "#9DB3A5"} stroke="#FFFFFF" strokeWidth={2}>
              <title>{`${c.company}: ${pct(c.requested_pct, 2)} requested (products ${pct(c.range_low_pct, 2)} to ${pct(c.range_high_pct, 2)})`}</title>
            </circle>
          );
        })}
        <line x1={rx} y1={40} x2={rx} y2={104} stroke="#4A5A50" strokeWidth={1.5} strokeDasharray="4 4" />
        <text x={rx} y={30} textAnchor={labelAnchor(rx)} fontSize={12} fill="#4A5A50">{referenceLabel} {pct(referencePct)}</text>
        {gx !== null && groupPct !== undefined && (
          <>
            <circle cx={gx} cy={90} r={10} fill="#1F3D2C" stroke="#FFFFFF" strokeWidth={3} />
            <text x={gx} y={146} textAnchor={labelAnchor(gx)} fontSize={13} fontWeight={600} fill="#16241C">This renewal {pct(groupPct)}</text>
          </>
        )}
      </svg>
      <figcaption className="text-xs leading-relaxed text-ink-3">
        Each dot is one carrier&apos;s average requested increase for 1/1/2027{band ? "; the shaded band is the selected carrier's product range" : ""}.
        Hover a dot for details. Source: ratereview.healthcare.gov, retrieved {filings.retrieved}. Requested rates, not final;
        regulators often approve less.
      </figcaption>
    </figure>
  );
}
