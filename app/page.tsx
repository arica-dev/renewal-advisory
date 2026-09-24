"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type GroupSummary, initials, longDate, money, pct, signedPct } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { Card, ErrorState, Pill, Skeleton, btn } from "@/components/ui";

type Filter = "all" | "review" | "sent";

export default function RenewalsPage() {
  const [groups, setGroups] = useState<GroupSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    setError(null);
    api.groups(ctl.signal).then(setGroups).catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    return () => ctl.abort();
  }, [attempt]);

  const stats = useMemo(() => {
    if (!groups?.length) return null;
    const sorted = [...groups].map((g) => g.total_pct).sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
    return {
      count: groups.length,
      enrolled: groups.reduce((s, g) => s + g.enrolled, 0),
      added: groups.reduce((s, g) => s + g.added_annual, 0),
      median,
      above: groups.filter((g) => g.verdict !== "within").length,
      marketMedian: groups[0]!.market_median_pct,
      date: groups[0]!.renewal_date,
      days: Math.min(...groups.map((g) => g.days_to_renewal)),
    };
  }, [groups]);

  const visible = (groups ?? []).filter((g) =>
    g.name.toLowerCase().includes(query.trim().toLowerCase()) &&
    (filter === "all" || (filter === "review" ? g.status !== "Brief sent" : g.status === "Brief sent")));

  const counts = {
    all: groups?.length ?? 0,
    review: groups?.filter((g) => g.status !== "Brief sent").length ?? 0,
    sent: groups?.filter((g) => g.status === "Brief sent").length ?? 0,
  };

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <p className="m-0 text-[13px] font-medium text-ink-2">Plan year 2027 · Pennsylvania small group</p>
          <h1 className="m-0 text-[34px] font-semibold tracking-tight">Renewals</h1>
        </div>
        <div className="flex gap-2.5">
          <label htmlFor="search" className="sr-only">Search groups</label>
          <input id="search" type="search" placeholder="Search groups" value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-h-11 w-60 rounded-xl border border-field bg-surface px-3.5 text-sm" />
          <button type="button" className={btn.primary} disabled title="Coming soon: upload a carrier renewal PDF">
            <Icon name="upload" size={16} /> Upload renewal
          </button>
        </div>
      </header>

      {error ? <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} /> : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {stats ? [
              { label: "Groups renewing", value: String(stats.count), note: `${stats.enrolled} enrolled · ${longDate(stats.date)}` },
              { label: "Added premium if accepted", value: money(stats.added), note: "per year, across all groups" },
              { label: "Median renewal increase", value: signedPct(stats.median), note: "aging and rate change combined" },
              { label: "Above the market median", value: `${stats.above} of ${stats.count}`, note: `rate change vs. ${pct(stats.marketMedian)} PA median` },
            ].map((s) => (
              <Card as="div" key={s.label} className="flex flex-col gap-2 rounded-2xl px-5 py-4">
                <span className="text-[13px] font-medium text-ink-2">{s.label}</span>
                <span className="num text-[28px] font-medium tracking-tight">{s.value}</span>
                <span className="text-xs text-ink-3">{s.note}</span>
              </Card>
            )) : Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[112px] rounded-2xl" />)}
          </div>

          <Card className="overflow-hidden rounded-2xl" aria-label="Renewing groups">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
              <div className="flex gap-1.5" role="group" aria-label="Filter">
                {([["all", "All"], ["review", "Needs review"], ["sent", "Brief sent"]] as const).map(([k, label]) => (
                  <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)}
                    className={`${btn.chip} ${filter === k ? "border-green bg-mint-soft font-semibold text-deep" : "border-field bg-surface text-ink-2 hover:bg-tint"}`}>
                    {label} · {counts[k]}
                  </button>
                ))}
              </div>
              {stats && <span className="text-[13px] text-ink-3">All renew {longDate(stats.date)} · {stats.days} days</span>}
            </div>
            <div className="hidden grid-cols-[2.2fr_1fr_1fr_1fr_1.6fr_1.1fr_24px] gap-4 border-b border-line px-5 py-3 text-xs font-semibold uppercase tracking-wider text-ink-3 md:grid">
              <div>Group</div><div>Enrolled</div><div>Carrier</div><div className="text-right">Increase</div>
              <div>Rate change vs. filings</div><div>Status</div><div />
            </div>
            {!groups && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="m-5 h-10" />)}
            {groups && visible.length === 0 && (
              <p className="m-0 px-5 py-10 text-center text-sm text-ink-3">No groups match.</p>
            )}
            {visible.map((g) => (
              <Link key={g.id} href={`/groups/${g.id}`}
                className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-line-2 px-5 py-[18px] text-ink no-underline transition-colors last:border-b-0 hover:bg-tint md:grid-cols-[2.2fr_1fr_1fr_1fr_1.6fr_1.1fr_24px]">
                <div className="flex items-center gap-3">
                  <div className="flex size-9 items-center justify-center rounded-[10px] bg-mint-soft text-[13px] font-bold text-deep">{initials(g.name)}</div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[15px] font-semibold">{g.name}</span>
                    <span className="text-xs text-ink-3">{g.size} employees</span>
                  </div>
                </div>
                <div className="num hidden text-sm md:block">{g.enrolled}</div>
                <div className="hidden text-sm text-ink-2 md:block">{g.carrier}</div>
                <div className="num text-right text-[15px] font-medium">{signedPct(g.total_pct)}</div>
                <div className="hidden items-center gap-2 md:flex">
                  <Pill tone={g.verdict === "within" ? "green" : "amber"}>{g.verdict === "within" ? "In line" : "Push back"}</Pill>
                  <span className="num text-xs text-ink-2">{pct(g.pure_rate_pct)} vs {pct(g.market_median_pct)}</span>
                </div>
                <div className="hidden items-center gap-2 text-[13px] text-ink-2 md:flex">
                  <span className={`size-2 rounded-full ${g.status === "In review" ? "bg-green" : "bg-[#B7C2BA]"}`} />{g.status}
                </div>
                <Icon name="chevron" className="hidden text-ink-3 md:block" />
              </Link>
            ))}
          </Card>
        </>
      )}
    </>
  );
}
