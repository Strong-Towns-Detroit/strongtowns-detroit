import { validateMapScene, type MapScene } from '@strongtowns/graphics-browser';
import { isBundleId, loadBundle, parseRecipe, type BzaFilters, type BzaPublicationBundle } from './bza.ts';
export type MapPublication = { version: 1; bundle: string; scene: MapScene };
export type MapRecipe = { version: 2; template: 'map'; map: string; filters: BzaFilters; title: string; explanation: string; selected?: string };
export function parseMapRecipe(value: unknown): MapRecipe {
  const r = value as MapRecipe;
  if (!r || r.version !== 2 || r.template !== 'map' || !isBundleId(r.map)) throw new Error('Invalid map settings.');
  const old = parseRecipe({ ...r, version: 1, template: 'category', bundle: r.map, format: 'instagram' });
  if (r.selected !== undefined && (typeof r.selected !== 'string' || r.selected.length > 200)) throw new Error('Invalid case selection.');
  return { version: 2, template: 'map', map: r.map, filters: old.filters, title: old.title, explanation: old.explanation, selected: r.selected };
}
export function mapRecipeHash(recipe: MapRecipe) { return `#map=${encodeURIComponent(JSON.stringify(parseMapRecipe(recipe)))}`; }
export function mapRecipeFromHash(hash: string): MapRecipe | null {
  if (!hash) return null;
  if (hash.length > 24000 || !hash.startsWith('#map=')) throw new Error('Invalid saved map link.');
  return parseMapRecipe(JSON.parse(decodeURIComponent(hash.slice(5))));
}
export async function loadMap(id: string, signal?: AbortSignal): Promise<{ publication: MapPublication; bundle: BzaPublicationBundle }> {
  if (!isBundleId(id)) throw new Error('Invalid map identifier.');
  const response = await fetch(`/data/bza-maps/${id}.json`, { signal });
  if (!response.ok) throw new Error('The saved map is unavailable. Retry without changing its dataset.');
  const raw = await response.arrayBuffer();
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==id) throw new Error('The map does not match its saved source.');
  const publication = JSON.parse(new TextDecoder().decode(raw)) as MapPublication;
  if(publication.version!==1 || !isBundleId(publication.bundle)) throw new Error('Unsupported map publication.');
  validateMapScene(publication.scene);
  const bundle = await loadBundle(publication.bundle, signal);
  const mapped = new Set(bundle.cases.filter(c=>c.mapped).map(c=>c.id));
  if(publication.scene.symbols.length !== mapped.size || publication.scene.symbols.some(s=>!mapped.has(s.id))) throw new Error('The map and case records disagree.');
  return {publication,bundle};
}
