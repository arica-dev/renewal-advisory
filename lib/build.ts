// Types and fetchers for the Renewal Build service (Django, /api/build/*).
// Amounts arrive as strings with two decimals ("802.29").

export type Severity = "blocker" | "review" | "info";
export type Method = "auto" | "layout" | "claude";

export interface Source {
  page?: number; bbox?: [number, number, number, number] | null;
  sheet?: string; cell?: string; text?: string; verified?: boolean; edited?: boolean;
}
export interface Rate { label: string; amount: string; source?: Source }
export interface PacketPlan {
  key: string; current_plan_name: string; current_code?: string; renewal_plan_name: string;
  renewal_code?: string; status: "renews" | "renamed" | "replaced" | "modified" | "discontinued" | "new";
  notes?: string; deductible?: string | null; oop_max?: string | null;
  current_rate_21?: string | null; renewal_rate_21?: string | null; rates: Rate[];
  sources?: Record<string, Source>; clasp_plan_id?: string;
}
export interface Packet {
  carrier?: string | null; employer_name?: string | null; group_number?: string | null;
  effective_date: string; state?: string | null; plans: PacketPlan[];
}
export interface Fix {
  action: "set_rate" | "add_rate" | "set_effective_date"; label?: string; amount?: string; value?: string;
}
export interface Check {
  id: string; kind: string; severity: Severity; title: string; detail: string;
  plan: string | null; label: string | null; fix: Fix | null; can_keep: boolean;
}
export interface ClaspContext {
  group_id: string; employer_name: string; state: string; plan_year_start: string; renewal_date: string;
  enrolled: number;
  plans: { id: string; plan_name: string; metal_level: string | null; deductible: string; oop_max: string;
           base_rate_21: string; enrolled: number }[];
}
export interface Preview {
  current_monthly: number; renewal_monthly: number; total_pct: number; aging_pct: number;
  rate_pct: number; pure_rate_pct: number; rates_21: Record<string, string>; advisor_url: string;
}
export interface OpenEnrollment { start_date: string; end_date: string; enrollment_type: "passive" | "active" }
export interface PageImage { n: number; width: number; height: number; image: string }
export interface Sheet { name: string; rows: { cell: string; value: string | null }[][] }

export interface Extraction {
  filename: string; format: "pdf" | "xlsx";
  extractor: { method: "layout" | "claude"; model: string | null };
  packet: Packet; context: ClaspContext | null; checks: Check[]; preview: Preview | null;
  open_enrollment: OpenEnrollment; pages: PageImage[]; sheets: Sheet[];
}

export interface ClaspRequest {
  id: string; operation: string; method: string; path: string; purpose: string; ref: string | null;
  depends_on: string[]; doc: string; body: unknown; errors: string[];
}
export interface BuildOutput {
  api_version: string; headers: Record<string, string>; requests: ClaspRequest[]; valid: boolean;
  assumptions: string[]; preview: Preview | null;
}

export interface SampleSummary {
  id: string; employer: string; carrier: string; format: "pdf" | "xlsx"; filename: string;
  effective_date: string; plans: number; blurb: string;
}
export interface Health { ok: boolean; claude_available: boolean; model: string | null; clasp_api_version: string }

export class ApiError extends Error {
  constructor(message: string, public status: number, public data: unknown) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  let data: unknown = null;
  try { data = await res.json(); } catch { /* not json */ }
  if (!res.ok) {
    const d = data as { detail?: string } | null;
    const msg = d?.detail ?? (data ? Object.values(data as object).flat().join(" ") : `Request failed (${res.status})`);
    throw new ApiError(String(msg), res.status, data);
  }
  return data as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const buildApi = {
  health: (signal?: AbortSignal) => call<Health>("/api/build/health", { signal }),
  samples: (signal?: AbortSignal) => call<SampleSummary[]>("/api/build/samples", { signal }),
  sampleFileUrl: (id: string) => `/api/build/samples/${encodeURIComponent(id)}/file`,
  extractSample: (id: string, method: Method, signal?: AbortSignal) =>
    call<Extraction>(`/api/build/samples/${encodeURIComponent(id)}/extract`, { ...json({ method }), signal }),
  extractUpload: (file: File, method: Method) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("method", method);
    return call<Extraction>("/api/build/extract", { method: "POST", body: fd });
  },
  generate: (packet: Packet, kept: string[], open_enrollment: OpenEnrollment) =>
    call<BuildOutput>("/api/build/requests", json({ packet, kept, open_enrollment })),
};

export const usd = (s: string | number | null | undefined) =>
  s === null || s === undefined || s === "" ? "—"
    : Number(s).toLocaleString("en-US", { style: "currency", currency: "USD" });

export const usd0 = (s: string | number | null | undefined) =>
  s === null || s === undefined || s === "" ? "—"
    : Number(s).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export const UPLOAD_KEY = "renewal-build:upload";
