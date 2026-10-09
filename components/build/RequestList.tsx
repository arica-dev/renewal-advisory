"use client";

import { useState } from "react";
import type { BuildOutput, ClaspRequest } from "@/lib/build";
import { Icon } from "@/components/Icon";
import { Pill, btn } from "@/components/ui";

function bodyPreview(r: ClaspRequest): string {
  if (Array.isArray(r.body) && r.body.length > 6) {
    const head = JSON.stringify(r.body.slice(0, 3), null, 2).replace(/\n]$/, "");
    return `${head},\n  … ${r.body.length - 3} more rows\n]`;
  }
  return JSON.stringify(r.body, null, 2);
}

export function RequestList({ output, name }: { output: BuildOutput; name: string }) {
  const [copied, setCopied] = useState(false);
  const all = JSON.stringify({ headers: output.headers, requests: output.requests.map(
    ({ id, method, path, body, depends_on }) => ({ id, method, path, depends_on, body })) }, null, 2);

  async function copy() {
    try { await navigator.clipboard.writeText(all); setCopied(true); setTimeout(() => setCopied(false), 1600); }
    catch { /* clipboard unavailable */ }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([all], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}-renewal-build.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-mint-soft px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-semibold text-deep">
          <Icon name="check" size={16} />
          {output.requests.length} requests · {output.valid ? "all valid against Clasp's schemas" : "some failed validation"}
        </span>
        <div className="flex gap-2">
          <button type="button" className={btn.secondary} onClick={copy}><Icon name="copy" size={16} />{copied ? "Copied" : "Copy JSON"}</button>
          <button type="button" className={btn.secondary} onClick={download}><Icon name="download" size={16} />Download</button>
        </div>
      </div>

      <div className="rounded-xl border border-line bg-ground px-4 py-3">
        <p className="m-0 mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-3">Headers on every call</p>
        <pre className="num m-0 overflow-x-auto text-[12px] leading-relaxed text-ink-2">
          {Object.entries(output.headers).map(([k, v]) => `${k}: ${v}`).join("\n")}
        </pre>
      </div>

      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {output.requests.map((r) => (
          <li key={r.id}>
            <details className="group rounded-xl border border-line bg-surface">
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
                <span className="num w-5 text-xs text-ink-3">{r.id}</span>
                <Pill tone="mint" className="num">{r.method}</Pill>
                <span className="num min-w-0 flex-1 truncate text-[13px] text-ink">{r.path}</span>
                <span className="text-[13px] text-ink-2">{r.purpose}</span>
                {r.errors.length ? <Pill tone="amber">{r.errors.length} error{r.errors.length > 1 ? "s" : ""}</Pill>
                  : <Pill tone="green"><Icon name="check" size={13} /> Valid</Pill>}
              </summary>
              <div className="flex flex-col gap-2 border-t border-line-2 px-4 py-3">
                {r.depends_on.length > 0 && <p className="m-0 text-xs text-ink-3">After call {r.depends_on.join(", ")} · uses the ID it returns</p>}
                {r.errors.map((e) => <p key={e} className="m-0 text-xs text-amber">{e}</p>)}
                <pre className="num m-0 max-h-80 overflow-auto rounded-lg bg-ground p-3 text-[12px] leading-relaxed text-ink-2">{bodyPreview(r)}</pre>
                <a href={r.doc} target="_blank" rel="noreferrer" className="text-xs font-medium text-green">Clasp API reference ↗</a>
              </div>
            </details>
          </li>
        ))}
      </ol>

      <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[13px] text-ink-2">
        {output.assumptions.map((a) => <li key={a}>{a}</li>)}
      </ul>
    </div>
  );
}
