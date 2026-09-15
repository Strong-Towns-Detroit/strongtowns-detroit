/** Fetch failures and malformed records must not look like an empty dataset. */
export async function fetchJson(url: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Unable to load ${url} (${response.status}).`);
  return response.json();
}

export function records(value: unknown, strings: string[], numbers: string[]): Record<string, unknown>[] {
  if (!Array.isArray(value) || !value.every((row) => row && typeof row === "object"
    && strings.every((key) => typeof row[key] === "string")
    && numbers.every((key) => typeof row[key] === "number" && Number.isFinite(row[key])))) {
    throw new Error("The downloaded records have an unexpected format.");
  }
  return value;
}

export function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export type AtlasState = { q: string; category: string[]; outcome: string[]; year: string[]; case: string };
export function readAtlasState(search: string): AtlasState {
  const params = new URLSearchParams(search);
  return { q: params.get("q") ?? "", category: params.getAll("category"),
    outcome: params.getAll("outcome"), year: params.getAll("year"), case: params.get("case") ?? "" };
}
export function writeAtlasState(state: AtlasState, search = ""): string {
  const params = new URLSearchParams(search);
  for (const key of ["q", "category", "outcome", "year", "case"] as const) {
    params.delete(key);
    const values = Array.isArray(state[key]) ? state[key] : [state[key]];
    for (const value of values) if (value) params.append(key, value);
  }
  return params.toString();
}
