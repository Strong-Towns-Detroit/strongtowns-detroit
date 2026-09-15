import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { chromium, firefox, webkit } from "playwright";

let server, browser, origin;
before(async () => {
  origin = process.env.CIVIC_TEST_ORIGIN ?? "http://127.0.0.1:8788";
  if (!process.env.CIVIC_TEST_ORIGIN) {
    server = spawn(process.execPath, ["node_modules/vinext/dist/cli.js", "start", "--hostname", "127.0.0.1", "--port", "8788"], {
      env: { ...process.env, WRANGLER_LOG_PATH: process.env.WRANGLER_LOG_PATH ?? "/tmp/civic-wrangler", WRANGLER_SEND_METRICS: "false" },
      detached: true, stdio: ["ignore", "pipe", "pipe"],
    });
    let logs = "";
    server.stdout.on("data", (data) => { logs = (logs + data).slice(-8000); });
    server.stderr.on("data", (data) => { logs = (logs + data).slice(-8000); });
    let ready = false;
    for (let i = 0; i < 150; i++) {
      if (server.exitCode !== null) throw new Error(`Production server failed: ${logs}`);
      try { if ((await fetch(origin)).ok) { ready = true; break; } } catch {}
      await new Promise((done) => setTimeout(done, 200));
    }
    if (!ready) throw new Error(`Production server did not become ready: ${logs}`);
  }
  const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const engine = process.env.CIVIC_BROWSER_ENGINE ?? 'chromium';
  browser = await ({ chromium, firefox, webkit })[engine].launch({ headless: true, executablePath: process.env.CIVIC_BROWSER_PATH ?? (engine === 'chromium' && existsSync(chrome) ? chrome : undefined) });
});
after(async () => {
  await browser?.close();
  if (server && server.exitCode === null) {
    process.kill(-server.pid, "SIGTERM");
    await new Promise((done) => server.once("exit", done));
  }
});

const cases = [{ id: "case-1", caseNumber: "17-24", address: "1 Test Street", location: "Detroit", petitioner: "Applicant", proposal: "A duplex", category: "lot_dimensions", categoryLabel: "Lot dimensions", outcome: "granted", outcomeLabel: "Granted", firstDate: "2024-01-01", lastDate: "2024-01-01", appearances: 1, lat: 42.36, lon: -83.1, hearings: [{ date: "2024-01-01", status: "decided", decision: "Granted", file: "minutes.pdf", sourceUrl: "https://example.org/minutes.pdf" }] }];
const studioRecord = { ...cases[0], mapped: true };
const studioBundle = {
  version: 1,
  cases: [studioRecord, { ...studioRecord, id: 'case-2', caseNumber: '18-24', mapped: false, firstDate: '', category: 'unspecified', categoryLabel: 'Request not specified', outcome: 'unclassified', outcomeLabel: 'Outcome not classified' }],
  coverage: { firstDate: '2024-01-01', lastDate: '2024-01-01' },
  inputs: { fixture: { snapshot_id: 'pinned', manifest_sha256: 'a'.repeat(64), created_at: '2024-02-01' } },
};
const studioRaw = JSON.stringify(studioBundle);
const studioId = createHash('sha256').update(studioRaw).digest('hex');
async function studioFixture(page, body = studioRaw) {
  await page.route('**/data/bza-studio/latest.json', (route) => route.fulfill({ json: { version: 1, bundle: studioId } }));
  await page.route(`**/data/bza-studio/${studioId}.json`, (route) => route.fulfill({ contentType: 'application/json', body }));
}
async function downloaded(page, name) {
  const waiting = page.waitForEvent('download');
  await page.getByRole('button', { name, exact: true }).click();
  const file = await waiting;
  assert.equal(await file.failure(), null);
  return { file, bytes: await readFile(await file.path()) };
}

test('studio exports matching PNG/SVG/CSV/settings and restores shared choices on mobile', { timeout: 60000 }, async () => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await studioFixture(page);
  await page.goto(`${origin}/graphics/bza/`);
  await page.getByText('2 cases selected', { exact: true }).waitFor();
  await page.getByRole('button', { name: '2. Review summary', exact: true }).click();
  await page.getByRole('table').first().waitFor();
  assert.match(await page.locator('body').innerText(), /1 selected cases have no valid first hearing date/);
  await page.getByRole('button', { name: '3. Customize', exact: true }).click();
  await page.getByLabel('Headline', { exact: true }).fill('Our recorded cases');
  await page.getByRole('img').first().waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('button', { name: '4. Download', exact: true }).click();
  const { bytes: svg } = await downloaded(page, 'Download SVG 1');
  assert.match(svg.toString(), /data:font\/woff2;base64/);
  assert.match(svg.toString(), /Our recorded cases/);
  assert.match(svg.toString(), /Height|Lot dimensions/);
  const { file: pngFile, bytes: png } = await downloaded(page, 'Download PNG 1');
  assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  assert.equal(png.readUInt32BE(16), 1080); assert.equal(png.readUInt32BE(20), 1350);
  await pngFile.saveAs(`/tmp/civic-studio-${process.env.CIVIC_BROWSER_ENGINE ?? 'chromium'}.png`);
  const { bytes: csv } = await downloaded(page, 'Download summary CSV');
  assert.match(csv.toString(), /2 cases; 1 unmapped; 1 undated/);
  const { bytes: settings } = await downloaded(page, 'Save settings');
  assert.equal(JSON.parse(settings).bundle, studioId);
  assert.equal(JSON.parse(settings).title, 'Our recorded cases');
  await page.getByRole('button', { name: 'Copy graphic link', exact: true }).click();
  const url = await page.getByLabel('Graphic link', { exact: true }).inputValue();
  await page.goto(url);
  await page.getByText('2 cases selected', { exact: true }).waitFor();
  await page.getByRole('button', { name: '3. Customize', exact: true }).click();
  assert.equal(await page.getByLabel('Headline', { exact: true }).inputValue(), 'Our recorded cases');
  await page.getByLabel('Publishing format', { exact: true }).selectOption('instagram_story');
  await page.getByRole('button', { name: '4. Download', exact: true }).click();
  const story = await downloaded(page, 'Download PNG 1');
  assert.equal(story.bytes.readUInt32BE(20), 1920);
  await page.screenshot({ path: `/tmp/civic-studio-mobile-${process.env.CIVIC_BROWSER_ENGINE ?? 'chromium'}.png`, fullPage: true });
  await page.close();
});

test('studio handoff, year exclusions, empty results and text overflow are explicit', { timeout: 60000 }, async () => {
  const page = await browser.newPage();
  await studioFixture(page);
  await page.goto(`${origin}/graphics/bza/?from=atlas&q=Test&year=2024&category=Lot+dimensions`);
  await page.getByText('1 cases selected', { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Case coverage', { exact: true }).inputValue(), 'mapped');
  assert.equal(await page.getByLabel('Search cases', { exact: true }).inputValue(), 'Test');
  await page.getByRole('button', { name: 'Reset filters', exact: true }).click();
  await page.getByLabel('2024', { exact: true }).check();
  await page.getByRole('button', { name: '2. Review summary', exact: true }).click();
  assert.match(await page.locator('body').innerText(), /1 otherwise matching undated cases were excluded/);
  await page.getByRole('button', { name: '3. Customize', exact: true }).click();
  await page.getByLabel('Headline', { exact: true }).fill('W'.repeat(160));
  await page.getByRole('alert').filter({ hasText: 'too long' }).waitFor();
  assert.equal(await page.getByRole('img').count(), 0);
  await page.getByRole('button', { name: '1. Choose records', exact: true }).click();
  await page.getByLabel('Search cases', { exact: true }).fill('absent');
  await page.getByText(/No cases match these filters/).waitFor();
  await page.getByRole('button', { name: '4. Download', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'Download PNG 1', exact: true }).count(), 0);
  await page.close();
});

test('studio rejects tampered bundles, unavailable history and invalid recipes without replacing them', { timeout: 60000 }, async () => {
  const page = await browser.newPage();
  await studioFixture(page, '{}');
  await page.goto(`${origin}/graphics/bza/`);
  await page.getByRole('alert').filter({ hasText: 'does not match' }).waitFor();
  await page.route(`**/data/bza-studio/${studioId}.json`, (route) => route.fulfill({ body: studioRaw, contentType: 'application/json' }));
  await page.getByRole('button', { name: 'Retry data', exact: true }).click();
  await page.getByText('2 cases selected', { exact: true }).waitFor();
  const recipe = { version: 1, bundle: 'f'.repeat(64), filters: { q: '', years: [], categories: [], outcomes: [], mappedOnly: false }, template: 'count', format: 'instagram', title: 'Cases', explanation: '' };
  await page.route(`**/data/bza-studio/${recipe.bundle}.json`, (route) => route.fulfill({ status: 404 }));
  await page.goto(`${origin}/graphics/bza/#recipe=${encodeURIComponent(JSON.stringify(recipe))}`);
  await page.getByRole('alert').filter({ hasText: 'saved data bundle is unavailable' }).waitFor();
  assert.equal(await page.getByText('2 cases selected', { exact: true }).count(), 0);
  await page.goto(`${origin}/graphics/bza/#recipe=${encodeURIComponent(JSON.stringify({ ...recipe, version: 2 }))}`);
  await page.getByRole('alert').filter({ hasText: 'unsupported version' }).waitFor();
  await page.close();
});

test('studio retries font failures and imports settings with keyboard-accessible steps', { timeout: 60000 }, async () => {
  const page = await browser.newPage();
  await studioFixture(page);
  let failFonts = true;
  await page.route('**/fonts/inter-latin.woff2', (route) => failFonts ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.continue());
  await page.goto(`${origin}/graphics/bza/`);
  const customize = page.getByRole('button', { name: '3. Customize', exact: true });
  await customize.focus(); await page.keyboard.press('Enter');
  await page.getByRole('alert').filter({ hasText: 'Fonts could not load' }).waitFor();
  assert.equal(await page.locator('#studio-step').evaluate((el) => el === document.activeElement), true);
  failFonts = false;
  await page.getByRole('button', { name: 'Retry preview', exact: true }).click();
  await page.getByRole('img').first().waitFor();
  const imported = { version: 1, bundle: studioId, filters: { q: 'Test', years: [], categories: [], outcomes: [], mappedOnly: true }, template: 'count', format: 'instagram', title: 'A saved count', explanation: 'Mapped cases.' };
  await page.getByLabel('Open saved settings', { exact: true }).setInputFiles({ name: 'settings.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(imported)) });
  await page.getByText('1 cases selected', { exact: true }).waitFor();
  await page.getByRole('button', { name: '3. Customize', exact: true }).click();
  assert.equal(await page.getByLabel('Template', { exact: true }).inputValue(), 'count');
  assert.equal(await page.getByLabel('Headline', { exact: true }).inputValue(), 'A saved count');
  await page.getByRole('img').first().waitFor();
  assert.match(await page.getByRole('img').first().getAttribute('alt'), /1 recorded BZA cases/);
  await page.close();
});

test('published case bundle renders all templates without overflowing or dropping categories', { timeout: 60000 }, async () => {
  const latest = JSON.parse(await readFile('public/data/bza-studio/latest.json', 'utf8'));
  const actual = JSON.parse(await readFile(`public/data/bza-studio/${latest.bundle}.json`, 'utf8'));
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto(`${origin}/graphics/bza/`);
  await page.getByText(`${actual.cases.length} cases selected`, { exact: true }).waitFor();
  await page.getByRole('button', { name: '3. Customize', exact: true }).click();
  await page.getByRole('img').first().waitFor();
  const alt = (await page.getByRole('img').evaluateAll((images) => images.map((img) => img.alt))).join(' ');
  for (const label of new Set(actual.cases.map((row) => row.categoryLabel))) assert.ok(alt.includes(`${label}:`), label);
  assert.equal(await page.getByRole('alert').count(), 0);
  for (const template of ['outcome', 'count']) {
    await page.getByLabel('Template', { exact: true }).selectOption(template);
    await page.getByRole('img').first().waitFor();
    assert.equal(await page.getByRole('alert').count(), 0);
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('button', { name: '4. Download', exact: true }).click();
  const { file } = await downloaded(page, 'Download PNG 1');
  await file.saveAs(`/tmp/civic-studio-count-${process.env.CIVIC_BROWSER_ENGINE ?? 'chromium'}.png`);
  await page.close();
});


test('whole Detroit export is independent of camera and preserves saved selection', { timeout: 90000 }, async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${origin}/atlas/`);
  await page.locator('[data-map-ready="true"]').waitFor();
  assert.equal(await page.locator('.map-artwork [data-case-id]').count(), 408);
  await page.getByRole('button', {name:'Zoom in',exact:true}).click();
  const camera = await page.locator('.map-artwork').getAttribute('style');
  await page.getByRole('button', {name:'Create graphic',exact:true}).click();
  await page.locator('.export-preview svg').first().waitFor();
  assert.equal(await page.locator('.export-preview [data-case-id]').count(),408);
  const atlas = await page.locator('.map-artwork [data-case-id]').evaluateAll(nodes=>nodes.map(n=>[n.getAttribute('data-case-id'),n.getAttribute('cx'),n.getAttribute('cy'),n.getAttribute('r')]));
  const preview = await page.locator('.export-preview [data-case-id]').evaluateAll(nodes=>nodes.map(n=>[n.getAttribute('data-case-id'),n.getAttribute('cx'),n.getAttribute('cy'),n.getAttribute('r')]));
  assert.deepEqual(preview,atlas);
  const {bytes:png,file}=await downloaded(page,'Download Instagram PNG');
  assert.equal(png.readUInt32BE(16),1080);assert.equal(png.readUInt32BE(20),1350);
  await file.saveAs('/tmp/land-forum-instagram.png');
  await page.getByLabel('Headline',{exact:true}).fill('Our Detroit cases');
  await page.locator('.export-preview svg').first().waitFor();
  const {bytes}=await downloaded(page,'Save settings');const recipe=JSON.parse(bytes);
  assert.equal(recipe.version,2);assert.equal(recipe.title,'Our Detroit cases');assert.equal('camera' in recipe,false);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('.map-artwork').getAttribute('style'),camera);
  assert.equal(await page.getByRole('button',{name:'Create graphic',exact:true}).evaluate(el=>el===document.activeElement),true);
  await page.getByLabel('Primary request',{exact:true}).selectOption('Parking');
  assert.equal(await page.locator('.map-artwork [data-case-id]').count(),65);
  await page.getByRole('button',{name:'Create graphic',exact:true}).click();
  await page.locator('.export-preview svg').first().waitFor();
  assert.equal(await page.locator('.export-preview [data-case-id]').count(),65);
  await page.keyboard.press('Escape');
  await page.goto(`${origin}/atlas/#map=${encodeURIComponent(JSON.stringify(recipe))}`);
  await page.reload();await page.locator('[data-map-ready="true"]').waitFor();
  await page.getByRole('button',{name:'Create graphic',exact:true}).click();
  assert.equal(await page.getByLabel('Headline',{exact:true}).inputValue(),'Our Detroit cases');
  await page.close();
});

test('mobile atlas retains unmapped cases, empty selections, reduced motion and source details', {timeout:60000},async()=>{
  const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  await page.goto(`${origin}/atlas/`);await page.locator('[data-map-ready="true"]').waitFor();
  assert.equal(await page.locator('.case-list li').count(),417);
  await page.locator('.case-list button').first().click();await page.locator('.case-detail').waitFor();
  await page.reload();await page.locator('.case-detail').waitFor();
  await page.getByRole('button',{name:'Create graphic',exact:true}).click();await page.locator('.export-preview svg').first().waitFor();
  assert.equal(await page.locator('dialog').evaluate(el=>getComputedStyle(el).animationName),'none');
  await page.screenshot({path:'/tmp/land-forum-mobile.png',fullPage:true});
  await page.keyboard.press('Escape');
  await page.getByLabel('Search cases',{exact:true}).fill('no-such-case-xyz');await page.getByText('No cases match these filters.').waitFor();
  assert.equal(await page.getByRole('button',{name:'Create graphic',exact:true}).isDisabled(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.close();
});

test('map corruption leaves current records available and saved history never silently advances',{timeout:60000},async()=>{
  const page=await browser.newPage();
  await page.route('**/data/bza-maps/*.json',route=>route.request().url().endsWith('/latest.json')?route.continue():route.fulfill({json:{}}));
  await page.goto(`${origin}/atlas/`);await page.getByRole('alert').filter({hasText:'does not match'}).waitFor();
  await page.locator('.case-list button').first().waitFor();
  const invalid={version:2,template:'map',map:'f'.repeat(64),filters:{q:'',categories:[],outcomes:[],years:[],mappedOnly:false},title:'Historic cases',explanation:''};
  await page.goto(`${origin}/atlas/#map=${encodeURIComponent(JSON.stringify(invalid))}`);await page.reload();
  await page.getByRole('alert').waitFor();assert.equal(await page.locator('.case-list button').count(),0);
  await page.close();
});
