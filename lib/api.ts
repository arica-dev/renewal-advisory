// Types and fetchers for the Python API (api/index.py). Numbers arrive as
// floats rounded to cents; percentages to 2 decimals.

export type Verdict = "above_range" | "above_average" | "within";

export interface GroupSummary {
  id: string;
  name: string;
  size: number;
  enrolled: number;
  carrier: string;
  renewal_date: string;
  days_to_renewal: number;
  current_monthly: number;
  renewal_monthly: number;
  added_annual: number;
  total_pct: number;
  pure_rate_pct: number;
  market_median_pct: number;
  verdict: Verdict;
  status: string;
}

export interface EmployeeRow {
  id: string;
  name: string;
  coverage: string;
  plan_today: string;
  plan_renewal: string;
  pays_today: number;
  pays_renewal: number;
  change: number;
}

export interface Option {
  rank: number;
  design: string;
  target_plan_id: string | null;
  employee_only_pct: number;
  dependent_pct: number;
  feasible: boolean;
  violations: { employer_increase_pct?: number; employee_monthly_increase?: number };
  employer_annual: number;
  employer_change_pct: number;
  employees_paying_more: number;
  max_employee_increase: number;
  total_employee_monthly_change: number;
  moved_to_higher_deductible: number;
  target_deductible: number | null;
  employees: EmployeeRow[];
}

export interface Goals {
  max_employer_increase_pct: number;
  max_employee_monthly_increase: number;
  min_employee_only_pct: number;
  max_deductible: number | null;
  objective: "protect_employees" | "lowest_employer_cost";
  employee_only_pct: number;
  dependent_pct: number;
}

export interface Analysis {
  group: {
    id: string; name: string; size: number; enrolled: number; carrier: string;
    renewal_date: string; days_to_renewal: number; state: string; status: string;
  };
  plans: {
    id: string; name: string; metal: string | null; deductible: number | null;
    current_rate_21: number; renewal_rate_21: number; change_pct: number; enrolled: number;
  }[];
  breakdown: {
    current_monthly: number; renewal_monthly: number; aging: number; rate: number;
    total_change: number; total_pct: number; aging_pct: number; rate_pct: number;
    pure_rate_change_pct: number;
  };
  benchmark: {
    compare_to: string; against: string; group_rate_pct: number; reference_pct: number;
    range_low_pct: number; range_high_pct: number; gap_pct: number; verdict: Verdict;
    requested: boolean;
  };
  today: { employer_annual: number };
  accept_renewal: {
    employer_annual: number; employer_change_pct: number; employees_paying_more: number;
    max_employee_increase: number; employees: EmployeeRow[];
  };
  goals: Goals;
  search: { evaluated: number; any_feasible: boolean };
  options: Option[];
}

export interface Filings {
  state: string; market: string; plan_year: number; retrieved: string; source: string;
  requested_only: boolean; median_pct: number; low_pct: number; high_pct: number;
  carriers: { company: string; requested_pct: number; range_low_pct: number;
              range_high_pct: number; products: number; status: string }[];
}

export interface Brief {
  group: Analysis["group"];
  breakdown: Analysis["breakdown"];
  benchmark: Analysis["benchmark"];
  target: string;
  subject: string;
  title: string;
  table: { label: string; amount: number; pct: number }[];
  paragraphs: string[];
  source: string;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, cache: "no-store" });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(`Request failed: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function qs(params: Record<string, string | number | null | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const api = {
  groups: (signal?: AbortSignal) => get<GroupSummary[]>("/api/groups", signal),
  filings: (signal?: AbortSignal) => get<Filings>("/api/filings", signal),
  analysis: (id: string, params: Record<string, string | number | null>, signal?: AbortSignal) =>
    get<Analysis>(`/api/groups/${encodeURIComponent(id)}/analysis${qs(params)}`, signal),
  brief: (id: string, params: Record<string, string | null>, signal?: AbortSignal) =>
    get<Brief>(`/api/groups/${encodeURIComponent(id)}/brief${qs(params)}`, signal),
  briefPdfUrl: (id: string, params: Record<string, string | null>) =>
    `/api/groups/${encodeURIComponent(id)}/brief.pdf${qs(params)}`,
};

// ---- formatting ---------------------------------------------------------------

export const money = (n: number, cents = false) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD",
    minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 });

export const signedMoney = (n: number, cents = false) =>
  (n > 0 ? "+" : n < 0 ? "−" : "") + money(Math.abs(n), cents);

export const pct = (n: number, digits = 1) => `${n.toFixed(digits)}%`;
export const signedPct = (n: number, digits = 1) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}%`;

export const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });

export const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");

export const verdictLabel: Record<Verdict, string> = {
  above_range: "Strong case to push back",
  above_average: "Room to push back",
  within: "In line with filings",
};
