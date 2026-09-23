/**
 * Backend access layer.
 *
 * The API only ever serves pre-computed data (predictions are produced by the
 * background pipeline), so pages use ISR (`revalidate`) instead of per-visitor
 * live fetches. Every call degrades to `null` on failure so a stopped backend
 * can never break a page render or `next build`.
 */
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function apiPost<T>(path: string, body?: unknown): Promise<T | null> {
  return api<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "–";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}
