import Link from "next/link";
import type { Verdict } from "@/lib/api";
import { verdictLabel } from "@/lib/api";

export function Card({ children, className = "", as: Tag = "section", ...rest }:
  { children: React.ReactNode; className?: string; as?: "section" | "div" | "article" | "aside" } & React.HTMLAttributes<HTMLElement>) {
  return <Tag className={`rounded-[20px] border border-line bg-surface ${className}`} {...rest}>{children}</Tag>;
}

export function Pill({ children, tone = "neutral", className = "" }:
  { children: React.ReactNode; tone?: "neutral" | "mint" | "amber" | "green" | "outline"; className?: string }) {
  const tones = {
    neutral: "bg-line text-ink",
    mint: "bg-mint text-deep",
    amber: "bg-amber-soft text-amber",
    green: "bg-mint-soft text-deep",
    outline: "border border-line bg-surface text-ink-2",
  };
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]} ${className}`}>{children}</span>;
}

export function VerdictPill({ verdict }: { verdict: Verdict }) {
  return <Pill tone={verdict === "within" ? "green" : "amber"}>{verdictLabel[verdict]}</Pill>;
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-ink-2">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span aria-hidden="true">/</span>}
          {it.href ? <Link href={it.href} className="font-medium text-green no-underline hover:text-deep">{it.label}</Link>
                   : <span aria-current="page">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export const btn = {
  primary: "inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-deep px-5 text-sm font-semibold text-white no-underline transition-colors hover:bg-green disabled:opacity-50",
  secondary: "inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-[#C9D3CC] bg-surface px-5 text-sm font-semibold text-ink no-underline transition-colors hover:bg-tint",
  chip: "inline-flex min-h-9 items-center rounded-full border px-3.5 text-[13px] transition-colors",
};

export const field = "min-h-11 w-full rounded-xl border border-field bg-surface px-3 text-sm text-ink";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="flex flex-col items-start gap-3 p-6" role="alert">
      <p className="m-0 font-semibold">Couldn't load this.</p>
      <p className="m-0 text-sm text-ink-2">{message}. Is the API running (<code className="num">npm run api</code>)?</p>
      {onRetry && <button type="button" className={btn.secondary} onClick={onRetry}>Try again</button>}
    </Card>
  );
}

export function Skeleton({ className }: { className: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}
