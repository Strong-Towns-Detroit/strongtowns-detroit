'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { embeddedFontCss, pngBlob, renderGraphic, type GraphicPage } from '@strongtowns/graphics-browser';
import definitions from '../../../projects/graphics/src/graphics/bza-studio.json';
import { atlasFilters, bundleUrl, emptyFilters, isBundleId, loadBundle, parseRecipe, recipeFromHash, recipeLink, scopeNote, summarize, summaryCsv, validDate, type BzaFilters, type BzaGraphicRecipe, type BzaPublicationBundle } from '../lib/graphics/bza';
import { safeSourceUrl } from '../lib/atlas/data';
import { brand } from '../lib/tokens';

const steps = ['Choose records', 'Review summary', 'Customize', 'Download'];
let loadedFonts: Promise<string> | undefined;
function exportFonts() {
  // Cache successful loads; a rejected request must remain retryable.
  loadedFonts ??= (async () => {
    const css = await embeddedFontCss(['/fonts/inter-latin.woff2']);
    const source = css.match(/url\((data:font\/woff2;base64,[^)]+)\)/)?.[1];
    if (!source) throw new Error('Export fonts could not be prepared. Retry the preview.');
    const font = new FontFace('Studio Inter', `url(${source})`, { weight: '100 900', style: 'normal' });
    document.fonts.add(await font.load());
    return css;
  })().catch((error) => { loadedFonts = undefined; throw error; });
  return loadedFonts;
}
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
const textBlob = (text: string, type = 'text/plain') => new Blob([text], { type: `${type};charset=utf-8` });

function Choices({ label, options, selected, onChange }: { label: string; options: string[]; selected: string[]; onChange: (values: string[]) => void }) {
  return <fieldset className="studio-choices"><legend>{label}</legend>{[...new Set([...options, ...selected])].map((option) => <label key={option}><input type="checkbox" checked={selected.includes(option)} onChange={(e) => onChange(e.target.checked ? [...selected, option] : selected.filter((value) => value !== option))} />{option}</label>)}</fieldset>;
}
function Counts({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  return <table><caption>{title}</caption><thead><tr><th scope="col">Group</th><th scope="col">Cases</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td>{row.value}</td></tr>)}</tbody></table>;
}

export default function BzaGraphicStudio() {
  const [recipe, setRecipe] = useState<BzaGraphicRecipe | null>(null);
  const [bundle, setBundle] = useState<BzaPublicationBundle | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [step, setStep] = useState(0);
  const [pages, setPages] = useState<GraphicPage[]>([]);
  const [renderError, setRenderError] = useState('');
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [notice, setNotice] = useState('');
  const [reviewText, setReviewText] = useState(false);
  const [busy, setBusy] = useState(false);
  const [imported, setImported] = useState<BzaGraphicRecipe | null>(null);
  const [shareLink, setShareLink] = useState('');
  const focusStep = useRef(false);
  useLayoutEffect(() => {
    if (focusStep.current) { document.getElementById('studio-step')?.focus(); focusStep.current = false; }
  }, [step]);

  useEffect(() => {
    const controller = new AbortController();
    setError(''); setBundle(null); setPages([]);
    (async () => {
      let next = imported ?? recipeFromHash(window.location.hash);
      if (!next) {
        const response = await fetch('/data/bza-studio/latest.json', { signal: controller.signal });
        if (!response.ok) throw new Error('BZA graphic data is unavailable. Retry or contact the site maintainer.');
        const latest = await response.json();
        if (latest.version !== 1 || !isBundleId(latest.bundle)) throw new Error('The current BZA data reference is invalid.');
        next = { version: 1, bundle: latest.bundle, filters: new URLSearchParams(location.search).get('from') === 'atlas' ? atlasFilters(location.search) : emptyFilters(), template: 'category', format: 'instagram', title: definitions.templates.category.title, explanation: definitions.templates.category.explanation };
        next = parseRecipe(next);
      }
      const data = await loadBundle(next.bundle, controller.signal);
      if (!controller.signal.aborted) { setRecipe(next); setBundle(data); setReviewText(false); }
    })().catch((e) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e)); });
    return () => controller.abort();
  }, [attempt, imported]);

  useEffect(() => {
    const restore = () => { setImported(null); setAttempt((n) => n + 1); };
    window.addEventListener('hashchange', restore);
    return () => window.removeEventListener('hashchange', restore);
  }, []);

  const summary = useMemo(() => bundle && recipe ? summarize(bundle, recipe.filters) : null, [bundle, recipe]);
  const notes = bundle && recipe && summary ? scopeNote(recipe, bundle, summary) : '';
  useEffect(() => {
    let active = true;
    setPages([]); setRenderError('');
    if (!recipe || !summary || !summary.total || !bundle) return;
    const current = recipe, counts = summary;
    (async () => {
      const fontCss = await exportFonts();
      const context = document.createElement('canvas').getContext('2d');
      if (!context) throw new Error('Preview rendering is unavailable in this browser.');
      const rendered = renderGraphic({ kind: current.template === 'count' ? 'count' : 'bars', format: current.format, title: current.title, explanation: current.explanation, notes, total: counts.total, rows: current.template === 'outcome' ? counts.outcomes : counts.categories, brand: definitions.brand, countLabel: definitions.countLabel, theme: { background: brand[definitions.themeTokens.background as keyof typeof brand], foreground: brand[definitions.themeTokens.foreground as keyof typeof brand], accent: brand[definitions.themeTokens.accent as keyof typeof brand] } }, { fontCss, measure: (text, size) => { context.font = `${size === 54 ? 700 : 400} ${size}px "Studio Inter"`; return context.measureText(text).width; } });
      if (active) setPages(rendered);
    })().catch((e) => { if (active) setRenderError(e instanceof Error ? e.message : String(e)); });
    return () => { active = false; };
  }, [recipe, summary, notes, renderAttempt, bundle]);

  function update(change: Partial<BzaGraphicRecipe>) {
    if (!recipe) return;
    const next = { ...recipe, ...change };
    setRecipe(next); setPages([]); setNotice(''); setShareLink('');
    if (change.filters) setReviewText(true);
    // Replace while typing: Back should leave the editor rather than replay keystrokes.
    if (next.title.trim()) history.replaceState(null, '', recipeLink(next, location.origin));
  }
  function filters(change: Partial<BzaFilters>) { if (recipe) update({ filters: { ...recipe.filters, ...change } }); }
  function go(index: number) {
    if (index === step) document.getElementById('studio-step')?.focus();
    else { focusStep.current = true; setStep(index); }
  }
  async function importFile(file?: File) {
    if (!file) return;
    try {
      if (file.size > 24000) throw new Error('This settings file is too large. Choose an exported BZA settings JSON file.');
      const next = parseRecipe(JSON.parse(await file.text()));
      history.replaceState(null, '', recipeLink(next, location.origin));
      setImported(next); setStep(0); setNotice('Settings opened.');
    } catch (e) { setNotice(`Could not open settings: ${e instanceof Error ? e.message : e}`); }
  }
  async function exportPng(page: GraphicPage, index: number) {
    setBusy(true); setNotice('');
    try { download(await pngBlob(page), `detroit-bza-${recipe!.template}-${recipe!.bundle.slice(0, 12)}-${index + 1}.png`); }
    catch (e) { setNotice(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return <div className="bza-studio">
    <div className="studio-tools"><a href="/graphics/bza/">Start a new graphic</a><label>Open saved settings <input type="file" accept=".json,application/json" onChange={(e) => { void importFile(e.target.files?.[0]); e.target.value = ''; }} /></label></div>
    <p role="status">{notice}</p>
    {error ? <div role="alert"><p>{error}</p><button onClick={() => setAttempt((n) => n + 1)}>Retry data</button></div> : !bundle || !recipe || !summary ? <p role="status">Loading recorded BZA cases…</p> : <>
      <nav aria-label="Graphic steps" className="studio-steps">{steps.map((label, index) => <button key={label} aria-current={step === index ? 'step' : undefined} onClick={() => go(index)}>{index + 1}. {label}</button>)}</nav>
      <h2 id="studio-step" tabIndex={-1}>{steps[step]}</h2>
      <p className="studio-total" aria-live="polite"><strong>{summary.total.toLocaleString()} cases selected</strong> · {summary.mapped} mapped · {summary.total - summary.mapped} unmapped</p>
      {step === 0 && <section aria-label="Record filters">
        <label className="studio-field">Search cases<input type="search" value={recipe.filters.q} maxLength={200} placeholder="Address, petitioner, or case number" onChange={(e) => filters({ q: e.target.value })} /></label>
        <label className="studio-field">Case coverage<select aria-label="Case coverage" value={recipe.filters.mappedOnly ? 'mapped' : 'all'} onChange={(e) => filters({ mappedOnly: e.target.value === 'mapped' })}><option value="all">All recorded cases</option><option value="mapped">Mapped cases only (atlas scope)</option></select></label>
        <p>No boxes selected means all values. Years refer to the first recorded hearing, not every hearing a case attended.</p>
        <div className="studio-filter-grid">
          <Choices label="First recorded hearing year" options={[...new Set(bundle.cases.filter((r) => validDate(r.firstDate)).map((r) => r.firstDate.slice(0, 4)))].sort()} selected={recipe.filters.years} onChange={(years) => filters({ years })} />
          <Choices label="Primary request" options={[...new Set(bundle.cases.map((r) => r.categoryLabel))].sort()} selected={recipe.filters.categories} onChange={(categories) => filters({ categories })} />
          <Choices label="Recorded outcome" options={[...new Set(bundle.cases.map((r) => r.outcomeLabel))].sort()} selected={recipe.filters.outcomes} onChange={(outcomes) => filters({ outcomes })} />
        </div><button onClick={() => update({ filters: emptyFilters() })}>Reset filters</button>
      </section>}
      {!summary.total && <p role="status">No cases match these filters. Change or reset the filters before creating a graphic.</p>}
      {step === 1 && <section aria-label="Case summary">
        <p>Each case is counted once. A case may have multiple requests; the chart uses its existing primary-request classification. Parking combines supply and layout requests. Outcomes reflect the available record.</p>
        <p>The atlas and this studio use the same source records and category labels. <a href="/data/bza-studio/comparison.json">Review changes from the previous atlas publication</a>.</p>
        <p>{summary.undated} selected cases have no valid first hearing date. {summary.excludedUndated} otherwise matching undated cases were excluded by the year filter. {summary.unspecified} requests are unspecified; {summary.unclassified} outcomes are unclassified.</p>
        <p>Available minutes span {bundle.coverage.firstDate || 'unknown dates'} through {bundle.coverage.lastDate || 'unknown dates'}. This does not establish complete coverage of Detroit BZA cases.</p>
        <div className="studio-summary-grid"><Counts title="Primary requests" rows={summary.categories} /><Counts title="Recorded outcomes" rows={summary.outcomes} /></div>
        <details><summary>Inspect the {summary.total} selected records and their sources</summary><div className="studio-table-scroll"><table><thead><tr><th>Case</th><th>Location</th><th>First hearing</th><th>Primary request</th><th>Outcome</th><th>Sources</th></tr></thead><tbody>{summary.records.map((row) => <tr key={row.id}><th scope="row">{row.caseNumber}</th><td>{row.address}{!row.mapped && ' (unmapped)'}</td><td>{row.firstDate || 'Not recorded'}</td><td>{row.categoryLabel}</td><td>{row.outcomeLabel}</td><td>{row.hearings.length ? row.hearings.map((h, i) => <div key={i}>{safeSourceUrl(h.sourceUrl) ? <a href={safeSourceUrl(h.sourceUrl)!} target="_blank" rel="noreferrer">{h.file || h.date || 'Source minutes'}</a> : `${h.file || h.date || 'Minutes'} — source link unavailable`}</div>) : 'No source link recorded'}</td></tr>)}</tbody></table></div></details>
        <details><summary>Data provenance and downloads</summary><a href={bundleUrl(recipe.bundle)} download>Download this case bundle</a><p>Bundle SHA-256: <code>{recipe.bundle}</code></p><pre>{JSON.stringify(bundle.inputs, null, 2)}</pre></details>
      </section>}
      {step === 2 && <section aria-label="Graphic options">
        <label className="studio-field">Template<select aria-label="Template" value={recipe.template} onChange={(e) => { const template = e.target.value as BzaGraphicRecipe['template']; const old = definitions.templates[recipe.template], next = definitions.templates[template]; update({ template, title: recipe.title === old.title ? next.title : recipe.title, explanation: recipe.explanation === old.explanation ? next.explanation : recipe.explanation }); }}>{Object.entries(definitions.templates).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label>
        <label className="studio-field">Publishing format<select aria-label="Publishing format" value={recipe.format} onChange={(e) => update({ format: e.target.value as BzaGraphicRecipe['format'] })}><option value="instagram">Instagram feed · 1080 × 1350</option><option value="instagram_story">Instagram story · 1080 × 1920</option></select></label>
        <label className="studio-field">Headline<input value={recipe.title} maxLength={160} onChange={(e) => update({ title: e.target.value })} /></label>
        <label className="studio-field">Short explanation<textarea value={recipe.explanation} maxLength={240} rows={3} onChange={(e) => update({ explanation: e.target.value })} /></label>
        <p>Counts, category labels, source notes, and layout follow the template. Long charts become numbered images with the same scale.</p>
      </section>}
      {step >= 2 && <section aria-label="Graphic preview">
        {reviewText && <p role="status">Your filters changed. Review the headline and explanation to make sure they still describe these cases. <button onClick={() => setReviewText(false)}>I reviewed the wording</button></p>}
        {renderError ? <div role="alert"><p>{renderError}</p><button onClick={() => setRenderAttempt((n) => n + 1)}>Retry preview</button></div> : summary.total > 0 && !pages.length ? <p role="status">Preparing preview and fonts…</p> : null}
        <div className="studio-previews">{pages.map((page, index) => <figure key={index}><img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(page.svg)}`} alt={page.altText} width={page.width} height={page.height} /><figcaption>Image {index + 1} of {pages.length}</figcaption>{step === 3 && <><div className="studio-actions"><button disabled={busy || reviewText} onClick={() => void exportPng(page, index)}>Download PNG {index + 1}</button><button disabled={busy || reviewText} onClick={() => download(textBlob(page.svg, 'image/svg+xml'), `detroit-bza-${recipe.template}-${recipe.bundle.slice(0, 12)}-${index + 1}.svg`)}>Download SVG {index + 1}</button></div><label className="studio-field">Alt text for image {index + 1}<textarea readOnly rows={5} value={page.altText} /></label><button onClick={() => download(textBlob(page.altText), `detroit-bza-alt-text-${index + 1}.txt`)}>Download alt text {index + 1}</button></>}</figure>)}</div>
        {step === 3 && <><p>Download each numbered image for the complete chart. Alt text describes its values and scope.</p><div className="studio-actions"><button disabled={!pages.length || reviewText} onClick={() => download(textBlob(summaryCsv(recipe, summary, notes), 'text/csv'), 'detroit-bza-summary.csv')}>Download summary CSV</button><button disabled={!recipe.title.trim()} onClick={() => download(textBlob(JSON.stringify(parseRecipe(recipe), null, 2), 'application/json'), 'detroit-bza-settings.json')}>Save settings</button><button disabled={!recipe.title.trim()} onClick={async () => { const url = recipeLink(recipe, location.origin); setShareLink(url); try { await navigator.clipboard.writeText(url); setNotice('Graphic link copied.'); } catch { setNotice('Copy the link from the field below.'); } }}>Copy graphic link</button></div><p>Anyone with the link can see your wording and filters. Saved graphics reopen using this exact data bundle.</p>{shareLink && <label className="studio-field">Graphic link<input readOnly value={shareLink} onFocus={(e) => e.target.select()} /></label>}<p className="studio-scope">{notes}</p></>}
      </section>}
      <div className="studio-actions studio-next">{step > 0 && <button onClick={() => go(step - 1)}>Back</button>}{step < 3 && <button disabled={step >= 1 && !summary.total} onClick={() => go(step + 1)}>Continue to {steps[step + 1].toLowerCase()}</button>}</div>
    </>}
  </div>;
}
