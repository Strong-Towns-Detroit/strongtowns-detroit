#!/usr/bin/env node
/**
 * Freeze an interactive exhibit route into a print-ready board.
 *
 * The frozen output is not a second implementation of the map — it is the same
 * React tree and the same MapSpec, rendered headless at print scale. That is
 * what stops the poster and the page disagreeing, which is exactly how the
 * palette forked between the matplotlib exhibits and the website.
 *
 * The result keeps the shape of the existing conference bundle: a raster map
 * inside vector chrome. The chrome is real DOM text, so the PDF path carries
 * selectable type rather than outlines.
 *
 * Usage:
 *   node scripts/freeze_exhibit.mjs \
 *     --route /publications/minimum-lot-area/poster/ \
 *     --stem detroit-minimum-lot-size \
 *     [--base http://localhost:3000] [--scale 2] [--out <dir>] [--pdf]
 */

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(HERE, "..");

function arg(name, fallback) {
  // lastIndexOf, not indexOf: `npm run freeze:lot-area -- --stem other`
  // appends a second --stem after the one baked into the npm script, and the
  // later flag is the one the caller means.
  const index = process.argv.lastIndexOf(`--${name}`);
  return index > -1 ? process.argv[index + 1] : fallback;
}
const flag = (name) => process.argv.includes(`--${name}`);

const route = arg("route", "/publications/minimum-lot-area/poster/");
const stem = arg("stem", "exhibit");
const base = arg("base", "http://localhost:3000");
const scale = Number(arg("scale", "2"));
const outDir = resolve(arg("out", resolve(SITE, "public/exhibits")));
const readyTimeout = Number(arg("timeout", "120000"));

/**
 * Supersampling factor.
 *
 * The matplotlib exhibits draw at dpi 435 — about 4700px wide — and the result
 * is downscaled into a 2030px map well, so every parcel is averaged from
 * several source pixels and the block texture reads dense and solid. Rendering
 * WebGL at exactly the output resolution instead leaves visible cream between
 * one-pixel parcels. Drawing large and averaging down reproduces the printed
 * density rather than approximating it with a fill hack.
 */
const supersample = Number(arg("supersample", "2"));

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  args: [
    // Headless Chromium falls back to SwiftShader without this; the parcel
    // layer is 378k polygons and software rasterisation is unusably slow.
    "--use-gl=angle",
    "--enable-gpu-rasterization",
    "--ignore-gpu-blocklist",
    // Subpixel/LCD text antialiasing assumes an RGB-stripe display, so it is
    // wrong for a printed board regardless — and it was the only thing left
    // varying between renders: up to 65 pixels of glyph edge along the title,
    // never inside the map. Grayscale AA at integer positions is both correct
    // for print and reproducible.
    "--disable-lcd-text",
    "--disable-font-subpixel-positioning",
    "--force-color-profile=srgb",
  ],
});

const page = await browser.newPage({
  // The board is 1600x1100; capturing at deviceScaleFactor 2 reproduces the
  // 3200px-wide PNG the existing print bundle emits. Supersampling multiplies
  // that, and the extra resolution is averaged back out below.
  viewport: { width: 1600, height: 1100 },
  deviceScaleFactor: scale * supersample,
});

const problems = [];
page.on("pageerror", (e) => problems.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") problems.push(m.text());
});

/**
 * In-flight tile requests.
 *
 * A stable frame alone is not proof the map is finished: deck.gl loads tiles
 * asynchronously and there can be a quiet gap longer than any sampling window,
 * during which the frame looks settled and is not. Gating on "no tile fetch has
 * been outstanding for N consecutive samples" uses a signal that cannot be
 * quiet for the wrong reason.
 */
let inFlight = 0;
let lastActivity = Date.now();
const isTile = (r) => r.url().includes(".pmtiles");
page.on("request", (r) => {
  if (isTile(r)) {
    inFlight += 1;
    lastActivity = Date.now();
  }
});
for (const event of ["requestfinished", "requestfailed"]) {
  page.on(event, (r) => {
    if (isTile(r)) {
      inFlight = Math.max(0, inFlight - 1);
      lastActivity = Date.now();
    }
  });
}

const url = `${base}${route}`;
console.log(`Rendering ${url} at ${scale}x ...`);

await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

// The dev server's floating issue badge is position:fixed and lands inside the
// captured element. Harmless in production builds, fatal to a printed board.
await page.addStyleTag({
  content:
    "nextjs-portal, [data-nextjs-toast], #__next-build-watcher { display: none !important; }",
});

// Fonts first: capturing mid-swap would bake the fallback face into the board.
await page.evaluate(() => document.fonts.ready);

// Then every tile. MapCanvas flips this only once all layers report loaded.
await page.waitForFunction(
  () => Boolean(document.querySelector("[data-map-error]")) ||
    document.querySelector("[data-map-ready]")?.getAttribute("data-map-ready") === "true",
  undefined,
  { timeout: readyTimeout },
);
async function assertMapLoaded() {
  const error = await page.locator("[data-map-ready]").getAttribute("data-map-error");
  if (error) throw new Error(`Cannot export an incomplete map: ${error}`);
}
await assertMapLoaded();

/**
 * Wait for the drawn map to stop changing.
 *
 * `data-map-ready` is a fast gate, not a guarantee: deck.gl's onViewportLoad
 * fires per viewport, and fitBounds moves the camera once on mount, so the flag
 * can latch against the pre-fit viewport while a tile band is still arriving.
 * That made lot-width non-deterministic — two renders differed across 31,484
 * pixels in one strip at the top of the map.
 *
 * Hashing a downsample of the composited canvas and requiring it to hold steady
 * measures the thing actually required: a settled frame.
 */
async function frameFingerprint() {
  return page.evaluate(async () => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return null;
    const w = 400;
    const h = Math.max(1, Math.round((canvas.height / canvas.width) * w));
    const off = new OffscreenCanvas(w, h);
    const ctx = off.getContext("2d");
    ctx.drawImage(canvas, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, w, h);
    let hash = 2166136261;
    for (let i = 0; i < data.length; i += 4) {
      hash = (hash ^ data[i]) * 16777619;
      hash = (hash ^ data[i + 1]) * 16777619;
      hash = (hash ^ data[i + 2]) * 16777619;
    }
    return hash >>> 0;
  });
}

// Require BOTH signals to hold: an unchanging frame and no tile traffic.
// Either alone has produced a flaky capture — the frame gate let lot-width
// through mid-load, and after that was added the flakiness simply moved to
// lot-area.
const STABLE_SAMPLES = 4;
const SAMPLE_MS = 600;
const QUIET_MS = 1200;
let stable = 0;
let previous = null;
const settleDeadline = Date.now() + readyTimeout;
while (stable < STABLE_SAMPLES) {
  await page.waitForTimeout(SAMPLE_MS);
  const current = await frameFingerprint();
  const quiet = inFlight === 0 && Date.now() - lastActivity > QUIET_MS;
  stable = quiet && current !== null && current === previous ? stable + 1 : 0;
  previous = current;
  if (Date.now() > settleDeadline) {
    console.warn(
      `  warning: map still settling after ${readyTimeout}ms ` +
        `(inFlight=${inFlight}) — capturing anyway`,
    );
    break;
  }
}

const frame = page.locator(".ex-frame");
const count = await frame.count();
if (count !== 1) {
  await browser.close();
  throw new Error(`Expected exactly one .ex-frame, found ${count}`);
}

const png = resolve(outDir, `${stem}.png`);

/**
 * Capture until two consecutive captures are byte-identical.
 *
 * Predicting when the map has finished loading kept failing: gating on
 * `data-map-ready` let one tile band through, adding a frame-stability check
 * moved the flake from lot-width to lot-area, and adding a tile-network quiet
 * check still let the *first* run of a cold dev server differ from every run
 * after it — always the same band, always only the first render.
 *
 * Verifying the artifact instead of forecasting the input is the guarantee that
 * actually holds: if two captures taken apart in time agree, the frame was not
 * still changing.
 */
const MAX_CAPTURE_ATTEMPTS = 6;
await assertMapLoaded();
let raw = await frame.screenshot({ scale: "device" });
let confirmed = false;
for (let attempt = 1; attempt < MAX_CAPTURE_ATTEMPTS; attempt += 1) {
  await page.waitForTimeout(700);
  const again = await frame.screenshot({ scale: "device" });
  if (again.equals(raw)) {
    confirmed = true;
    break;
  }
  console.log(`  frame changed after capture — retrying (${attempt})`);
  raw = again;
}
if (!confirmed) {
  console.warn(
    `  warning: capture never stabilised in ${MAX_CAPTURE_ATTEMPTS} attempts`,
  );
}

if (supersample === 1) {
  await writeFile(png, raw);
} else {
  // Average the oversized render back down to the target board size. Done in
  // the page so Chromium's own resampler handles it — no native image
  // dependency, and identical output on any machine that can run the export.
  const targetWidth = 1600 * scale;
  const targetHeight = 1100 * scale;
  const encoded = await page.evaluate(
    async ({ data, targetWidth, targetHeight }) => {
      const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
      const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
      const canvas = new OffscreenCanvas(targetWidth, targetHeight);
      const ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight);
      const blob = await canvas.convertToBlob({ type: "image/png" });
      const buffer = new Uint8Array(await blob.arrayBuffer());
      let binary = "";
      for (const byte of buffer) binary += String.fromCharCode(byte);
      return btoa(binary);
    },
    { data: raw.toString("base64"), targetWidth, targetHeight },
  );
  await writeFile(png, Buffer.from(encoded, "base64"));
}
console.log(
  `  wrote ${png} (${1600 * scale}x${1100 * scale}` +
    (supersample > 1 ? `, supersampled ${supersample}x` : "") +
    ")",
);

if (flag("pdf")) {
  // 16in x 11in matches the @page size the HTML bundle already declares.
  const pdf = resolve(outDir, `${stem}.pdf`);
  await page.pdf({
    path: pdf,
    width: "16in",
    height: "11in",
    printBackground: true,
    pageRanges: "1",
  });
  console.log(`  wrote ${pdf}`);
}

await browser.close();

if (problems.length) {
  console.error(`\n${problems.length} page error(s) during render:`);
  [...new Set(problems)].slice(0, 10).forEach((p) => console.error("  " + p));
  process.exitCode = 1;
} else {
  console.log("\nNo page errors.");
}
