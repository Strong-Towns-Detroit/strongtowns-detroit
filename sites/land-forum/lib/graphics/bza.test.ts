import { test } from 'node:test';
import assert from 'node:assert/strict';
import { atlasFilters, emptyFilters, parseBundle, parseRecipe, recipeFromHash, recipeLink, scopeNote, summarize, summaryCsv, validDate, type BzaCase, type BzaGraphicRecipe, type BzaPublicationBundle } from './bza.ts';
const row: BzaCase = { id: '1', caseNumber: '17-24', address: '1 Test Street', location: 'Detroit', petitioner: 'Applicant', proposal: '', category: 'height', categoryLabel: 'Height', outcome: 'granted_reversed', outcomeLabel: 'Request granted', firstDate: '2024-01-01', lastDate: '2025-01-01', mapped: true, hearings: [] };
const bundle: BzaPublicationBundle = { version: 1, cases: [row, { ...row, id: '2', firstDate: '2023-12-31', mapped: false }, { ...row, id: '3', firstDate: '', category: 'unspecified', categoryLabel: 'Request not specified', outcome: 'unclassified', outcomeLabel: 'Outcome not classified' }], coverage: { firstDate: '2023-12-31', lastDate: '2025-01-01' }, inputs: { test: { snapshot_id: 'pinned', manifest_sha256: 'a'.repeat(64), created_at: '2025-01-01' } } };
const recipe: BzaGraphicRecipe = { version: 1, bundle: 'a'.repeat(64), filters: emptyFilters(), template: 'category', format: 'instagram', title: 'Cases', explanation: 'Each case once.' };
test('all-case counts include unmapped and undated cases with unknown groups', () => {
  const s = summarize(bundle, emptyFilters());
  assert.equal(s.total, 3); assert.equal(s.mapped, 2); assert.equal(s.undated, 1); assert.equal(s.unspecified, 1); assert.equal(s.unclassified, 1);
  assert.deepEqual(s.categories, [{ label: 'Height', value: 2 }, { label: 'Request not specified', value: 1 }]);
  assert.equal(s.categories.reduce((a, b) => a + b.value, 0), s.total);
  assert.equal(s.outcomes.reduce((a, b) => a + b.value, 0), s.total);
});
test('year boundaries use first hearing, combine with filters, and report excluded undated cases', () => {
  const s = summarize(bundle, { ...emptyFilters(), years: ['2023', '2024'], q: 'test', outcomes: ['Request granted'] });
  assert.equal(s.total, 2);
  assert.equal(summarize(bundle, { ...emptyFilters(), years: ['2024'] }).excludedUndated, 1);
  assert.equal(summarize(bundle, { ...emptyFilters(), years: ['2025'] }).total, 0);
  assert.equal(summarize(bundle, { ...emptyFilters(), years: ['2023'], mappedOnly: true }).total, 0);
  assert.equal(validDate('2024-02-30'), false);
  assert.equal(validDate('2024-02-29'), true);
});
test('atlas handoff preserves nonconsecutive years, label filters, search and mapped scope', () => {
  assert.deepEqual(atlasFilters('?year=2021&year=2024&category=Height&outcome=Request+granted&q=Test&case=1'), { q: 'Test', years: ['2021', '2024'], categories: ['Height'], outcomes: ['Request granted'], mappedOnly: true });
});
test('recipes round-trip with unicode and reject malformed versions and identifiers', () => {
  const original = { ...recipe, title: 'Detroit’s cases & “requests”' };
  assert.deepEqual(recipeFromHash(new URL(recipeLink(original, 'https://example.org')).hash), original);
  assert.deepEqual(parseRecipe(JSON.parse(JSON.stringify(original))), original);
  assert.throws(() => parseRecipe({ ...recipe, version: 2 }), /unsupported/);
  assert.throws(() => parseRecipe({ ...recipe, bundle: '../other' }), /invalid/);
  assert.throws(() => parseRecipe({ ...recipe, filters: { ...emptyFilters(), years: ['yesterday'] } }), /filters/);
  assert.throws(() => recipeFromHash('#broken'), /invalid/);
});
test('bundle contract rejects duplicates and incomplete provenance', () => {
  assert.deepEqual(parseBundle(bundle), bundle);
  assert.throws(() => parseBundle({ ...bundle, cases: [row, row] }), /duplicate/);
  assert.throws(() => parseBundle({ ...bundle, inputs: {} }), /unexpected/);
});
test('CSV includes exact counts, scope and immutable identity', () => {
  const s = summarize(bundle, recipe.filters), notes = scopeNote(recipe, bundle, s);
  const csv = summaryCsv(recipe, s, notes);
  assert.match(csv, /"Height","2"/); assert.match(csv, /3 cases; 1 unmapped; 1 undated/);
  assert.ok(csv.includes(recipe.bundle));
  const unsafe = { ...s, categories: [{ label: '=1+1', value: 3 }] };
  assert.match(summaryCsv(recipe, unsafe, notes), /"'=1\+1"/);
});

test('historical atlas and studio retain identical mapped cases and filter results', async () => {
  const { readFile } = await import('node:fs/promises');
  const { matchesBzaCase } = await import('./bza.ts');
  const root = new URL('../../public/data/', import.meta.url);
  const latest = { bundle: '87c2229baa36a5b8ed6493692128351a6ed0c6945ca3ff5d0e3d9eacdff689c9' };
  const published = parseBundle(JSON.parse(await readFile(new URL(`bza-studio/${latest.bundle}.json`, root), 'utf8')));
  const atlas: BzaCase[] = JSON.parse(await readFile(new URL('bza-cases.json', root), 'utf8'));
  const ids = (records: { id: string }[]) => records.map((row) => row.id).sort();
  assert.deepEqual(ids(atlas), ids(published.cases.filter((row) => row.mapped)));
  for (const category of new Set(atlas.map((row) => row.categoryLabel))) {
    const filters = { ...emptyFilters(), categories: [category], mappedOnly: true };
    assert.deepEqual(ids(atlas.filter((row) => matchesBzaCase(row, filters))), ids(summarize(published, filters).records));
  }
  for (const outcome of new Set(atlas.map((row) => row.outcomeLabel))) {
    const filters = { ...emptyFilters(), outcomes: [outcome], mappedOnly: true };
    assert.deepEqual(ids(atlas.filter((row) => matchesBzaCase(row, filters))), ids(summarize(published, filters).records));
  }
});
