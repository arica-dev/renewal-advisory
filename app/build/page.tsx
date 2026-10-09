"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { initials } from "@/lib/api";
import { buildApi, shortDate, type Health, type Method, type SampleSummary, UPLOAD_KEY } from "@/lib/build";
import { Icon } from "@/components/Icon";
import { Card, ErrorState, Pill, Skeleton, btn } from "@/components/ui";

const STEPS = [
  ["Read", "Rates, plans and dates pulled from the carrier's PDF or spreadsheet, each traced to where it's printed."],
  ["Check", "Every rate tested against the ACA age curve; dates and plans compared with what Clasp has."],
  ["Map", "Renamed and replaced plans confirmed by a person, so members land on the right plan."],
  ["Build", "The Clasp API calls that set up the new plan year and open enrollment, validated before they're sent."],
] as const;

export default function BuildPage() {
  const router = useRouter();
  const [samples, setSamples] = useState<SampleSummary[] | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("layout");
  const [busy, setBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const ctl = new AbortController();
    setError(null);
    Promise.all([buildApi.samples(ctl.signal), buildApi.health(ctl.signal)])
      .then(([s, h]) => { setSamples(s); setHealth(h); if (h.claude_available) setMethod("claude"); })
      .catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    return () => ctl.abort();
  }, [attempt]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setUploadError(null);
    try {
      const result = await buildApi.extractUpload(file, method);
      try { sessionStorage.setItem(UPLOAD_KEY, JSON.stringify(result)); } catch { /* storage unavailable */ }
      router.push("/build/upload");
    } catch (e) {
      setUploadError((e as Error).message);
      setBusy(false);
    }
  }

  const claude = health?.claude_available ?? false;

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <p className="m-0 text-[13px] font-medium text-ink-2">Plan year 2027 · Carrier renewals</p>
        <h1 className="m-0 text-[34px] font-semibold tracking-tight">Renewal build</h1>
        <p className="m-0 max-w-2xl text-[15px] leading-relaxed text-ink-2">
          Turn a carrier&apos;s renewal packet into a ready-to-load plan year in Clasp. The packet is read,
          every rate is checked, plan changes are confirmed by a person, and the output is the exact
          API calls that build the renewal and open enrollment.
        </p>
      </header>

      <ol className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(([title, text], i) => (
          <li key={title} className="flex flex-col gap-1.5 rounded-2xl border border-line bg-surface px-4 py-3.5">
            <span className="text-[13px] font-semibold"><span className="num text-green">{i + 1}</span> · {title}</span>
            <span className="text-[13px] leading-relaxed text-ink-2">{text}</span>
          </li>
        ))}
      </ol>

      {error ? <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} /> : (
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Card className="overflow-hidden rounded-2xl" aria-label="Packets waiting">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <h2 className="m-0 text-base font-semibold">Packets waiting</h2>
              <span className="text-[13px] text-ink-3">Samples · fictional carrier and rates</span>
            </div>
            {!samples && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="m-5 h-12" />)}
            {samples?.map((s) => (
              <Link key={s.id} href={`/build/${s.id}?method=${method}`}
                className="grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-line-2 px-5 py-4 text-ink no-underline transition-colors last:border-b-0 hover:bg-tint">
                <div className="flex size-9 items-center justify-center rounded-[10px] bg-mint-soft text-[13px] font-bold text-deep">{initials(s.employer)}</div>
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-[15px] font-semibold">{s.employer}</span>
                    <Pill tone="outline" className="num uppercase">{s.format}</Pill>
                  </span>
                  <span className="text-[13px] text-ink-2">{s.blurb}</span>
                  <span className="text-xs text-ink-3">{s.carrier} · {s.plans} plans · printed effective {shortDate(s.effective_date)}</span>
                </div>
                <Icon name="chevron" className="text-ink-3" />
              </Link>
            ))}
          </Card>

          <Card className="flex flex-col gap-4 rounded-2xl p-5" aria-label="Upload a packet">
            <h2 className="m-0 text-base font-semibold">Upload a packet</h2>
            <div role="group" aria-label="Read packets with" className="flex flex-col gap-2">
              <span className="text-[13px] font-medium text-ink-2">Read packets with</span>
              <div className="flex gap-1.5">
                {([["claude", "Claude"], ["layout", "Built-in parser"]] as const).map(([m, label]) => (
                  <button key={m} type="button" aria-pressed={method === m} disabled={m === "claude" && !claude}
                    onClick={() => setMethod(m)}
                    className={`${btn.chip} disabled:cursor-not-allowed disabled:opacity-50 ${method === m ? "border-green bg-mint-soft font-semibold text-deep" : "border-field bg-surface text-ink-2 hover:bg-tint"}`}>
                    {label}
                  </button>
                ))}
              </div>
              <p className="m-0 text-xs leading-relaxed text-ink-3">
                {health === null ? "Checking…" : claude
                  ? `Claude (${health.model}) reads any carrier's layout; every value is checked back against the document.`
                  : "Claude isn't connected on this server (no ANTHROPIC_API_KEY), so only the sample carrier layout can be read."}
              </p>
            </div>
            <button type="button" disabled={busy}
              onClick={() => input.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}
              className="flex min-h-36 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-sage bg-tint px-4 text-center text-sm text-ink-2 transition-colors hover:bg-mint-soft disabled:opacity-60">
              <Icon name="upload" size={22} className="text-green" />
              <span className="font-semibold text-ink">{busy ? (method === "claude" ? "Claude is reading the packet…" : "Reading the packet…") : "Choose or drop a renewal packet"}</span>
              <span className="text-xs text-ink-3">PDF or .xlsx, up to 4 MB</span>
            </button>
            <input ref={input} type="file" accept=".pdf,.xlsx" className="sr-only" aria-label="Renewal packet file"
              onChange={(e) => upload(e.target.files?.[0])} />
            {uploadError && <p role="alert" className="m-0 rounded-xl bg-amber-soft px-3 py-2 text-[13px] text-amber">{uploadError}</p>}
            {samples && (
              <p className="m-0 text-xs text-ink-3">
                Try it with a sample:{" "}
                {samples.map((s, i) => (
                  <span key={s.id}>{i > 0 && " · "}<a href={buildApi.sampleFileUrl(s.id)} download className="font-medium text-green">{s.filename}</a></span>
                ))}
              </p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
