/** Export through the same preview and PNG path as the public atlas. */
import { chromium } from 'playwright';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
const [origin, settings, output] = process.argv.slice(2);
if (!origin || !output) throw new Error('Usage: node scripts/export_bza_map.mjs <site-origin> <settings.json|latest> <output.png>');
const url = new URL('/atlas/', origin);
if (settings !== 'latest') url.hash = `map=${encodeURIComponent(await readFile(settings, 'utf8'))}`;
const browser = await chromium.launch({headless:true});
try {
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto(url.href);
 await page.getByRole('button',{name:'Create graphic',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.export-preview svg') || document.querySelector('dialog [role="alert"]'));
 const error = page.locator('dialog [role="alert"]');
 if(await error.count())throw new Error(await error.innerText());
 const download=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download Instagram PNG',exact:true}).click();
 await mkdir(dirname(output),{recursive:true});
 await (await download).saveAs(output);
 console.log(`Saved ${output}`);
} finally {await browser.close();}
