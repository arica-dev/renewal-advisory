import type { Takeaway } from "@/lib/api";
import { Card } from "@/components/ui";

// Figures worth scanning for: money, percentages, "3.6 points", "2 of 27". Years and plan names stay plain.
const FIGURE = /(\$[\d,]+(?:\.\d+)?(?:\/month)?|[+−-]?\d+(?:\.\d+)?%|\d+(?:\.\d+)? points|\d+ of \d+)/g;

function withFigures(text: string) {
  return text.split(FIGURE).map((part, i) =>
    i % 2 === 1 ? <span key={i} className="font-semibold text-ink tabular-nums">{part}</span> : part);
}

/** The conclusion a broker takes into the client meeting. All text comes from the API. */
export function Takeaways({ summary, items }: { summary: string; items: Takeaway[] }) {
  return (
    <Card className="flex flex-col gap-6 p-6" aria-labelledby="bottom-line">
      <div className="flex flex-col gap-2">
        <h2 id="bottom-line" className="m-0 text-[13px] font-medium text-ink-2">Bottom line</h2>
        <p className="m-0 max-w-3xl text-[22px] font-semibold leading-snug tracking-tight">{summary}</p>
      </div>
      <dl className="m-0 grid gap-5 border-t border-line pt-5 lg:grid-cols-3 lg:gap-8">
        {items.map((t) => (
          <div key={t.id} className="flex flex-col gap-1.5">
            <dt className="text-[13px] font-medium text-ink-3">{t.title}</dt>
            <dd className="m-0 text-sm leading-relaxed text-ink-2">{withFigures(t.text)}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
