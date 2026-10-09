"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { buildApi, type Extraction, type Method, UPLOAD_KEY } from "@/lib/build";
import { Breadcrumbs, Card, ErrorState, Skeleton, btn } from "@/components/ui";
import { BuildReview } from "@/components/build/BuildReview";
import Link from "next/link";

function methodFromUrl(): Method {
  if (typeof window === "undefined") return "auto";
  const m = new URLSearchParams(window.location.search).get("method");
  return m === "claude" || m === "layout" ? m : "auto";
}

export default function BuildPacketPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<Extraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("auto");
  const [attempt, setAttempt] = useState(0);

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
    const m = methodFromUrl();
    setMethod(m);
    const ctl = new AbortController();
    buildApi.extractSample(id, m, ctl.signal).then(setResult)
      .catch((e) => { if (!ctl.signal.aborted) setError(String(e.message)); });
    return () => ctl.abort();
  }, [id, attempt]);

  return (
    <>
      <Breadcrumbs items={[{ label: "Renewal build", href: "/build" }, { label: result?.context?.employer_name ?? result?.packet.employer_name ?? "Packet" }]} />
      {error ? (
        id === "upload" ? (
          <Card className="flex flex-col items-start gap-3 p-6" role="alert">
            <p className="m-0 font-semibold">{error}.</p>
            <Link href="/build" className={btn.secondary}>Back to Renewal build</Link>
          </Card>
        ) : <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />
      ) : result ? <BuildReview result={result} /> : (
        <div className="flex flex-col gap-4" aria-busy="true">
          <p className="m-0 text-sm text-ink-2" role="status">
            {method === "claude" ? "Claude is reading the packet and every rate table…" : "Reading the packet…"}
          </p>
          <Skeleton className="h-20" />
          <Skeleton className="h-48" />
          <Skeleton className="h-72" />
        </div>
      )}
    </>
  );
}
