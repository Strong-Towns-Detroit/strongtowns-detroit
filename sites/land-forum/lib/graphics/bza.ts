import { readAtlasState } from '../atlas/data.ts';

export type BzaCase = { id: string; caseNumber: string; address: string; location: string; petitioner: string; proposal: string; category: string; categoryLabel: string; outcome: string; outcomeLabel: string; firstDate: string; lastDate: string; mapped: boolean; hearings: { date: string; file: string; sourceUrl: string | null }[] };
export type BzaPublicationBundle = { version: 1; cases: BzaCase[]; coverage: { firstDate: string; lastDate: string }; inputs: Record<string, { snapshot_id: string; manifest_sha256: string; created_at: string }> };
export type BzaFilters = { q: string; years: string[]; categories: string[]; outcomes: string[]; mappedOnly: boolean };
export type BzaGraphicRecipe = { version: 1; bundle: string; filters: BzaFilters; template: 'category' | 'outcome' | 'count'; format: 'instagram' | 'instagram_story'; title: string; explanation: string };
export type GraphicSummary = { records: BzaCase[]; total: number; mapped: number; undated: number; excludedUndated: number; unspecified: number; unclassified: number; categories: { label: string; value: number }[]; outcomes: { label: string; value: number }[] };
export const emptyFilters = (): BzaFilters => ({ q: '', years: [], categories: [], outcomes: [], mappedOnly: false });
export const isBundleId = (s: unknown): s is string => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
export const bundleUrl = (id: string) => { if (!isBundleId(id)) throw new Error('Invalid data bundle identifier.'); return `/data/bza-studio/${id}.json`; };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const string = (v: unknown, max = 1000): v is string => typeof v === 'string' && v.length <= max;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 100 && v.every((s) => string(s, 150));
export const validDate = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;

export function parseRecipe(value: unknown): BzaGraphicRecipe {
  if (!object(value) || value.version !== 1 || !isBundleId(value.bundle) || !['category', 'outcome', 'count'].includes(String(value.template)) || !['instagram', 'instagram_story'].includes(String(value.format)) || !string(value.title, 160) || !value.title.trim() || !string(value.explanation, 240)) throw new Error('These settings are invalid or use an unsupported version. Open a version 1 BZA settings file.');
  const f = value.filters;
  if (!object(f) || !string(f.q, 200) || !strings(f.years) || !f.years.every((y) => /^\d{4}$/.test(y)) || !strings(f.categories) || !strings(f.outcomes) || typeof f.mappedOnly !== 'boolean') throw new Error('The saved filters are invalid.');
  return { version: 1, bundle: value.bundle, template: value.template as BzaGraphicRecipe['template'], format: value.format as BzaGraphicRecipe['format'], title: value.title, explanation: value.explanation, filters: { q: f.q, years: [...new Set(f.years)], categories: [...new Set(f.categories)], outcomes: [...new Set(f.outcomes)], mappedOnly: f.mappedOnly } };
}
export function parseBundle(value: unknown): BzaPublicationBundle {
  if (!object(value) || value.version !== 1 || !Array.isArray(value.cases) || !object(value.coverage) || !string(value.coverage.firstDate) || !string(value.coverage.lastDate) || !object(value.inputs) || !Object.keys(value.inputs).length) throw new Error('The BZA data bundle has an unexpected format.');
  for (const input of Object.values(value.inputs)) if (!object(input) || !string(input.snapshot_id) || !isBundleId(input.manifest_sha256) || !string(input.created_at)) throw new Error('The BZA source information is incomplete.');
  const ids = new Set<string>();
  for (const row of value.cases) {
    if (!object(row) || !['id', 'caseNumber', 'address', 'location', 'petitioner', 'proposal', 'category', 'categoryLabel', 'outcome', 'outcomeLabel', 'firstDate', 'lastDate'].every((key) => typeof row[key] === 'string') || !row.id || ids.has(row.id as string) || typeof row.mapped !== 'boolean' || !Array.isArray(row.hearings) || !row.hearings.every((h) => object(h) && string(h.date) && string(h.file) && (h.sourceUrl === null || string(h.sourceUrl)))) throw new Error('The BZA records are invalid or contain duplicate case IDs.');
    ids.add(row.id as string);
  }
  return value as BzaPublicationBundle;
}
export async function loadBundle(id: string, signal?: AbortSignal): Promise<BzaPublicationBundle> {
  const response = await fetch(bundleUrl(id), { signal });
  if (!response.ok) throw new Error('This saved data bundle is unavailable. Retry, or explicitly start a new graphic with current data.');
  const raw = await response.arrayBuffer();
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', raw)), (b) => b.toString(16).padStart(2, '0')).join('');
  if (hash !== id) throw new Error('The data does not match this graphic’s saved source. Retry or contact the site maintainer.');
  return parseBundle(JSON.parse(new TextDecoder().decode(raw)));
}
export function matchesBzaCase(row: Pick<BzaCase, 'caseNumber' | 'address' | 'location' | 'petitioner' | 'categoryLabel' | 'outcomeLabel' | 'firstDate'>, filters: Omit<BzaFilters, 'mappedOnly'>): boolean {
  const q = filters.q.trim().toLowerCase();
  return (!q || [row.caseNumber, row.address, row.location, row.petitioner].join(' ').toLowerCase().includes(q))
    && (!filters.categories.length || filters.categories.includes(row.categoryLabel))
    && (!filters.outcomes.length || filters.outcomes.includes(row.outcomeLabel))
    && (!filters.years.length || (validDate(row.firstDate) && filters.years.includes(row.firstDate.slice(0, 4))));
}
export function summarize(bundle: BzaPublicationBundle, filters: BzaFilters): GraphicSummary {
  const base = bundle.cases.filter((row) => (!filters.mappedOnly || row.mapped)
    && matchesBzaCase(row, { ...filters, years: [] }));
  const records = base.filter((row) => matchesBzaCase(row, filters));
  const group = (key: 'categoryLabel' | 'outcomeLabel') => {
    const counts = new Map<string, number>();
    for (const row of records) counts.set(row[key], (counts.get(row[key]) ?? 0) + 1);
    return [...counts].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label, 'en'));
  };
  return { records, total: records.length, mapped: records.filter((r) => r.mapped).length, undated: records.filter((r) => !validDate(r.firstDate)).length, excludedUndated: filters.years.length ? base.filter((r) => !validDate(r.firstDate)).length : 0, unspecified: records.filter((r) => r.category === 'unspecified').length, unclassified: records.filter((r) => r.outcome === 'unclassified').length, categories: group('categoryLabel'), outcomes: group('outcomeLabel') };
}
export function atlasFilters(search: string): BzaFilters {
  const state = readAtlasState(search);
  return { q: state.q, years: state.year, categories: state.category, outcomes: state.outcome, mappedOnly: true };
}
export function recipeLink(recipe: BzaGraphicRecipe, origin: string) {
  return `${origin}/graphics/bza/#recipe=${encodeURIComponent(JSON.stringify(parseRecipe(recipe)))}`;
}
export function recipeFromHash(hash: string) {
  if (!hash) return null;
  if (hash.length > 24000 || !hash.startsWith('#recipe=')) throw new Error('This graphic link is invalid.');
  return parseRecipe(JSON.parse(decodeURIComponent(hash.slice(8))));
}
export function scopeNote(recipe: BzaGraphicRecipe, bundle: BzaPublicationBundle, summary: GraphicSummary): string {
  const f = recipe.filters;
  const selections = [f.mappedOnly ? 'Mapped cases only' : 'All recorded cases', f.years.length ? `First recorded hearing: ${[...f.years].sort().join(', ')}` : 'All recorded hearing years', f.categories.length ? `Request: ${f.categories.join(', ')}` : '', f.outcomes.length ? `Outcome: ${f.outcomes.join(', ')}` : '', f.q ? `Search: “${f.q}”` : ''].filter(Boolean).join('. ');
  return `${selections}. ${summary.total} cases; ${summary.total - summary.mapped} unmapped; ${summary.undated} undated. Source: available Detroit BZA minutes, ${bundle.coverage.firstDate || 'date unknown'}–${bundle.coverage.lastDate || 'date unknown'}. Each case once; primary request (parking grouped); outcomes as recorded. Coverage may be incomplete. Data: ${recipe.bundle.slice(0, 12)}.`;
}
export function summaryCsv(recipe: BzaGraphicRecipe, summary: GraphicSummary, notes: string) {
  const cell = (v: unknown) => `"${String(v).replace(/^[=+@\-\t\r]/, "'$&").replace(/"/g, '""')}"`;
  const rows = recipe.template === 'count' ? [{ label: 'Recorded cases', value: summary.total }] : recipe.template === 'category' ? summary.categories : summary.outcomes;
  return [['Label', 'Cases', 'Scope and source', 'Bundle SHA-256'], ...rows.map((r) => [r.label, r.value, notes, recipe.bundle])].map((r) => r.map(cell).join(',')).join('\r\n');
}
