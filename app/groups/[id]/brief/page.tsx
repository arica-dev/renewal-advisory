"use client";

import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { api, type Brief, type Filings, signedMoney } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { Breadcrumbs, Card, ErrorState, Pill, Skeleton, btn, field } from "@/components/ui";

const MARKET = "market";

export default function BriefPage() {
  return <Suspense fallback={<Skeleton className="h-[600px] rounded-[20px]" />}><BriefView /></Suspense>;
}

function BriefView() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const [compareTo, setCompareTo] = useState(search.get("compare_to") ?? MARKET);
  const [target, setTarget] = useState("");
  const [sender, setSender] = useState("");
  const [recipient, setRecipient] = useState("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [filings, setFilings] = useState<Filings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    api.filings(ctl.signal).then(setFilings).catch(() => {});
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    const t = setTimeout(() => {
      setError(null);
      api.brief(id, { compare_to: compareTo, target: target.trim() || null }, ctl.signal)
        .then(setBrief).catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    }, 250);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [id, compareTo, target, attempt]);

  if (error) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (!brief) return <Skeleton className="h-[600px] rounded-[20px]" />;

  const from = sender.trim() || "[Broker name], [Agency]";
  const to = recipient.trim() || `[${brief.group.carrier} account manager]`;
  const pdfUrl = api.briefPdfUrl(id, { compare_to: compareTo, target: target.trim() || null, sender: from, recipient: to });

  const emailText = [
    `Subject: ${brief.subject}`, "", brief.title, "", brief.paragraphs[0]!, "",
    ...brief.table.map((r) => `- ${r.label}: ${signedMoney(r.amount)}/mo (${r.pct.toFixed(1)}%)`), "",
    brief.paragraphs[1]!, "", brief.paragraphs[2]!, "", "Thank you,", from, "", `Source: ${brief.source}`,
  ].join("\n");

  const copy = async () => {
    try { await navigator.clipboard.writeText(emailText); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { setCopied(false); }
  };

  return (
    <>
      <header className="flex flex-col gap-3.5">
        <Breadcrumbs items={[{ label: "Renewals", href: "/" }, { label: brief.group.name, href: `/groups/${id}` }, { label: "Push-back brief" }]} />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 text-[34px] font-semibold tracking-tight">Push-back brief</h1>
            <p className="m-0 text-sm text-ink-2">Drafted from the renewal analysis. Edit the settings; the letter updates.</p>
          </div>
          <Pill tone="mint">Draft · not sent</Pill>
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card as="article" aria-label="Brief preview" className="flex flex-col gap-5 px-7 py-10 text-[15px] leading-relaxed md:px-14 md:py-12">
          <dl className="m-0 grid grid-cols-[64px_minmax(0,1fr)] gap-y-1.5 border-b border-line pb-5 text-sm text-ink-2">
            <dt>To</dt><dd className="m-0 text-ink">{to}</dd>
            <dt>From</dt><dd className="m-0 text-ink">{from}</dd>
            <dt>Re</dt><dd className="m-0 text-ink">{brief.subject}</dd>
          </dl>
          <h2 className="m-0 text-[22px] font-semibold tracking-tight">{brief.title}</h2>
          <p className="m-0">{brief.paragraphs[0]}</p>
          <div className="overflow-hidden rounded-[14px] border border-line">
            {brief.table.map((r, i) => (
              <div key={r.label} className={`grid grid-cols-[minmax(0,1fr)_130px_80px] gap-4 border-b border-line-2 px-4 py-3 last:border-b-0 ${
                i === brief.table.length - 1 ? "bg-tint font-semibold" : ""}`}>
                <span>{r.label}</span>
                <span className="num text-right">{signedMoney(r.amount)}/mo</span>
                <span className="num text-right">{r.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <p className="m-0">{brief.paragraphs[1]}</p>
          <p className="m-0">{brief.paragraphs[2]}</p>
          <p className="m-0">Thank you,<br />{from}</p>
          <p className="m-0 border-t border-line pt-4 text-xs text-ink-3">Source: {brief.source}</p>
        </Card>

        <aside aria-label="Brief settings" className="flex flex-col gap-4 lg:sticky lg:top-6">
          <Card as="div" className="flex flex-col gap-4 p-5">
            <h2 className="m-0 text-base font-semibold">Settings</h2>
            <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">From
              <input className={field} placeholder="[Broker name], [Agency]" value={sender} onChange={(e) => setSender(e.target.value)} maxLength={120} />
            </label>
            <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">To
              <input className={field} placeholder={`[${brief.group.carrier} account manager]`} value={recipient} onChange={(e) => setRecipient(e.target.value)} maxLength={120} />
            </label>
            <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Benchmark
              <select className={field} value={compareTo} onChange={(e) => setCompareTo(e.target.value)}>
                <option value={MARKET}>PA market median</option>
                {filings?.carriers.map((c) => c.company).sort().map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">Target rate change
              <input className={field} placeholder={brief.target} value={target} onChange={(e) => setTarget(e.target.value)} maxLength={80} />
            </label>
          </Card>
          <div className="flex flex-col gap-2.5">
            <a href={pdfUrl} className={btn.primary}><Icon name="download" size={16} /> Download PDF</a>
            <button type="button" className={btn.secondary} onClick={copy} aria-live="polite">
              <Icon name={copied ? "check" : "copy"} size={16} /> {copied ? "Copied" : "Copy as email"}
            </button>
            <Link href={`/groups/${id}`} className="py-3 text-center text-sm font-semibold text-green no-underline hover:text-deep">
              Back to analysis
            </Link>
          </div>
        </aside>
      </div>
    </>
  );
}
