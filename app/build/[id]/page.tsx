"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { buildApi, type Extraction, type Method, UPLOAD_KEY } from "@/lib/build";
import { Breadcrumbs, Card, ErrorState, Skeleton, btn } from "@/components/ui";
import { BuildReview } from "@/components/build/BuildReview";

function methodFromUrl(): Method {
  if (typeof window === "undefined") return "layout";
  const m = new URLSearchParams(window.location.search).get("method");
  return m === "claude" || m === "auto" ? m : "layout";
}

/** Seconds since loading started, so a Claude read never looks like a hang. */
function Elapsed({ running }: { running: boolean }) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    setS(0);
    const t = setInterval(() => setS((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  return <span className="num">{s}s</span>;
}

export default function BuildPacketPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<Extraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("layout");
  const [claude, setClaude] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    buildApi.health(ctl.signal).then((h) => setClaude(h.claude_available)).catch(() => {});
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    setError(null);
    setResult(null);
    if (id === "upload") {
      try {
        const raw = sessionStorage.getItem(UPLOAD_KEY);
        if (raw) setResult(JSON.parse(raw) as Extraction);
        else setError("No uploaded packet in this tab. Upload it again from Renewal build");
      } catch {
        setError("Couldn't read the uploaded packet. Upload it again from Renewal build");
      }
      return;
    }
    const m = attempt === 0 ? methodFromUrl() : method;
    setMethod(m);
    const ctl = new AbortController();
    buildApi.extractSample(id, m, ctl.signal).then(setResult)
      .catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, attempt]);

  function readWith(m: Method) {
    setMethod(m);
    window.history.replaceState(null, "", `?method=${m}`);
    setAttempt((n) => n + 1);
  }

  const loading = !result && !error;
  const reread = id !== "upload" && result && (
    result.extractor.method === "layout"
      ? claude && <button type="button" className={btn.secondary} onClick={() => readWith("claude")}>Re-read with Claude</button>
      : <button type="button" className={btn.secondary} onClick={() => readWith("layout")}>Use built-in parser</button>
  );

  return (
    <>
      <Breadcrumbs items={[{ label: "Renewal build", href: "/build" }, { label: result?.context?.employer_name ?? result?.packet.employer_name ?? "Packet" }]} />
      {error ? (
        id === "upload" ? (
          <Card className="flex flex-col items-start gap-3 p-6" role="alert">
            <p className="m-0 font-semibold">{error}.</p>
            <Link href="/build" className={btn.secondary}>Back to Renewal build</Link>
          </Card>
        ) : <ErrorState message={error} hint={false} onRetry={() => setAttempt((n) => n + 1)} />
      ) : result ? <BuildReview key={`${result.extractor.method}-${attempt}`} result={result} actions={reread || null} /> : (
        <div className="flex flex-col gap-4" aria-busy="true">
          <p className="m-0 text-sm text-ink-2" role="status">
            {method === "claude"
              ? <>Claude is reading the packet and every rate table · <Elapsed running={loading} />. Usually under a minute; if it runs long, the built-in parser takes over.</>
              : "Reading the packet…"}
          </p>
          <Skeleton className="h-20" />
          <Skeleton className="h-48" />
          <Skeleton className="h-72" />
        </div>
      )}
    </>
  );
}
