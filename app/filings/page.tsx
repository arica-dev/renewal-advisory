"use client";

import { useEffect, useState } from "react";
import { api, type Filings, pct } from "@/lib/api";
import { BenchmarkStrip } from "@/components/BenchmarkStrip";
import { Card, ErrorState, Skeleton } from "@/components/ui";

export default function FilingsPage() {
  const [f, setF] = useState<Filings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    setError(null);
    api.filings(ctl.signal).then(setF).catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    return () => ctl.abort();
  }, [attempt]);

  if (error) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;

  const rows = f ? [...f.carriers].sort((a, b) => b.requested_pct - a.requested_pct) : [];

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <p className="m-0 text-[13px] font-medium text-ink-2">Pennsylvania · small group · plan year 2027</p>
        <h1 className="m-0 text-[34px] font-semibold tracking-tight">Rate filings</h1>
        <p className="m-0 max-w-2xl text-sm leading-relaxed text-ink-2">
          Every carrier&apos;s requested average rate change, the benchmark behind each push-back. All are requested
          (submission filed), not final.
        </p>
      </header>
      {!f ? <Skeleton className="h-[500px] rounded-[20px]" /> : (
        <>
          <Card className="p-6">
            <BenchmarkStrip filings={f} referencePct={f.median_pct} referenceLabel="Median" />
          </Card>
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <caption className="sr-only">2027 Pennsylvania small-group rate filings</caption>
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-ink-3">
                  <th scope="col" className="px-6 py-3 font-semibold">Carrier</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">Requested</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">Product range</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">Products</th>
                  <th scope="col" className="px-6 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.company} className="border-b border-line-2 last:border-b-0">
                    <th scope="row" className="px-6 py-3 text-left font-medium">{c.company}</th>
                    <td className="num px-4 py-3 text-right">{pct(c.requested_pct, 2)}</td>
                    <td className="num px-4 py-3 text-right text-ink-2">{pct(c.range_low_pct, 2)} to {pct(c.range_high_pct, 2)}</td>
                    <td className="num px-4 py-3 text-right text-ink-2">{c.products}</td>
                    <td className="px-6 py-3 text-ink-2">{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="m-0 text-xs text-ink-3">
            Source: <a href={f.source}>ratereview.healthcare.gov</a>, retrieved {f.retrieved}. Median {pct(f.median_pct, 2)}, range {pct(f.low_pct, 2)} to {pct(f.high_pct, 2)}.
          </p>
        </>
      )}
    </>
  );
}
