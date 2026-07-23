"""Fetch and parse the Michigan STC Form 625 "Ad Valorem Property Tax Levy
Report" series and extract City-level Taxable Value for Detroit and Flint.

Why this exists
---------------
Michigan Proposal A (1994) caps annual growth of a parcel's *taxable value*
(TV) at the lesser of 5% or an inflation multiplier, but imposes no floor on
the way down: when the market falls, State Equalized Value (SEV, ~50% of true
cash value) falls and TV follows it down at full speed. On recovery, SEV snaps
back at market speed while TV is throttled to <=5%/yr. Only a *sale* uncaps a
parcel. The result: a city's tax base craters fast in a downturn and recovers
on a decades-long capped schedule.

This is the asymmetry Jon Wylie / Joel Arnold described for Flint. The Form 625
series is the authoritative, machine-parseable spine for demonstrating it: one
PDF per year, 1996-2025, giving each local unit's total taxable value.

CAUTION — the City/Township trap
--------------------------------
Each report lists a TOWNSHIPS section and a CITIES section. Genesee County has
*both* a "Flint" city and a "Flint" (Charter) Township with similar magnitudes.
A naive grep for "FLINT" grabs whichever comes first (the township) — a real
error made by an upstream data scout on this project. Rather than slicing out the
CITIES section, this parser exploits the row *layout* to pick the city (see
``parse_city_tv``), and asserts every parse against hand-verified anchors so a
mis-parse fails loudly rather than silently reporting the wrong municipality.

Format change: pre-2016 reports left-align city rows (``DETROIT   8,301,...``)
while township rows are county-prefixed and indented — so a column-0 bare-name
match is unambiguously the city. 2019+ reports county-prefix every row
(``Wayne   Detroit   8,889,...``), and cities always follow townships — so the
LAST county-prefixed match for the name is the city.

Output: data/ad_valorem_city_tv.csv  (city, tax_year, taxable_value, source_url)
Run:    python fetch_ad_valorem.py   (needs `pdftotext` on PATH — poppler)
"""

from __future__ import annotations

import csv
import html
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

INDEX_URL = (
    "https://www.michigan.gov/taxes/property/reports/"
    "ad-valorem-property-tax-levy-reports"
)
BASE = "https://www.michigan.gov"
# michigan.gov WAFs default urllib/curl UAs with HTTP 403; a browser UA passes.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "data" / "pdf"
OUT_CSV = HERE / "data" / "ad_valorem_city_tv.csv"

# Pre-2004 reports use an older layout this parser mis-reads (e.g. Detroit 1997
# extracts as ~$0), and no verified anchor exists that far back. The entire
# question at hand is a 2007-crash phenomenon, so restrict the canonical series
# to the consistent, spot-verified 2004+ era. Extending earlier is future work
# that needs its own anchors.
MIN_YEAR = 2004

# Hand-verified City-level taxable value (dollars). Any parsed year that
# collides with one of these must match exactly, or we raise. Sourced by
# manual inspection of the CITIES section of each report.
ANCHORS = {
    ("Detroit", 2007): 9_468_676_802,
    ("Detroit", 2008): 10_031_267_735,
    ("Detroit", 2013): 8_301_190_480,
    # 2016-2018 added after an audit caught a levy-year mislabel; cross-checked
    # to the dollar against the independent ACFR Schedule-5 series.
    ("Detroit", 2016): 6_414_231_487,
    ("Detroit", 2017): 6_038_052_029,
    ("Detroit", 2018): 6_113_711_044,
    ("Detroit", 2019): 6_309_949_756,
    ("Detroit", 2024): 8_889_357_685,
    ("Detroit", 2025): 9_347_338_694,
    ("Flint", 2007): 1_693_727_807,
    ("Flint", 2008): 1_643_424_483,
    ("Flint", 2013): 776_654_903,
    ("Flint", 2016): 710_934_838,
    ("Flint", 2017): 714_582_817,
    ("Flint", 2018): 733_885_761,
    ("Flint", 2019): 742_647_433,
    ("Flint", 2024): 969_273_616,
    ("Flint", 2025): 1_055_175_591,
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def scrape_report_urls() -> list[str]:
    """Scrape the index page for every ad-valorem levy-report PDF URL.

    Returns a de-duplicated URL list. We deliberately do NOT infer the year from
    the filename: some transitional reports are named PUB_LEVY (e.g.
    ``2019_2018_625_...`` = *levy* 2018, published 2019), so a filename-first-year
    heuristic silently collides levy-2018 with the levy-2019 report and drops one.
    The authoritative year is read from each PDF's own title page (see
    ``levy_year``)."""
    idx = _get(INDEX_URL).decode("utf-8", "replace")
    seen: set[str] = set()
    urls: list[str] = []
    for m in re.finditer(r'href="([^"]+?\.pdf[^"]*)"', idx, re.I):
        href = html.unescape(m.group(1))
        fname = href.rsplit("/", 1)[-1]
        if not re.search(r"valorem|levy", fname, re.I):
            continue
        if not re.search(r"(19|20)\d{2}", fname):
            continue
        full = href if href.startswith("http") else BASE + href
        key = full.split("?")[0]
        if key not in seen:
            seen.add(key)
            urls.append(full)
    return urls


def levy_year(text: str) -> int | None:
    """The levy (tax) year, read from the report's title page — the first
    plausible year in the header. Excludes the 'Public Act 140 of 1971' statutory
    reference by the lower bound (Proposal A began 1994; the series starts 1996)."""
    head = "\n".join(text.splitlines()[:15])
    for m in re.finditer(r"\b(?:19|20)\d{2}\b", head):
        y = int(m.group(0))
        if 1994 <= y <= 2027:
            return y
    return None


def fetch_pdf_by_url(url: str) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("?")[0].rsplit("/", 1)[-1])
    dst = PDF_DIR / base
    if dst.exists() and dst.stat().st_size > 30_000:
        return dst
    data = _get(url)
    if len(data) < 30_000:
        raise RuntimeError(f"response too small ({len(data)}b) for {url}")
    dst.write_bytes(data)
    return dst


def pdf_to_text(pdf: Path) -> str:
    txt = pdf.with_suffix(".txt")
    if not txt.exists():
        subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(txt)],
            check=True, capture_output=True,
        )
    return txt.read_text("utf-8", "replace")


_NUM = r"[\d,]{7,}"  # >= 7 chars w/ commas => >= ~$1M, i.e. a valuation column


def parse_city_tv(text: str, city: str) -> int | None:
    """Return the City's total taxable value, disambiguated from the same-named
    township, or None.

    The report lists a statewide TOWNSHIPS section then a CITIES section. Two
    row layouts occur across the series, and each gives a clean city/township
    discriminator:

    * pre-2016 ("old"): city rows are LEFT-ALIGNED at column 0
      (``DETROIT   8,301,190,480``); township rows are county-prefixed and
      indented (``   GENESEE   FLINT   821,958,020``). So a column-0 match on the
      bare city name is the city — the township can't match it.
    * 2019+ ("new"): every row is county-prefixed
      (``Wayne   Detroit   8,889,357,685``); ``Genesee Flint`` therefore appears
      twice — once in townships, once in cities. Cities always follow townships,
      so the LAST county-prefixed match is the city.
    """
    # Old format: bare city name at column 0 (no leading whitespace/county).
    m = re.search(rf"^{re.escape(city)}\s+({_NUM})\b", text, re.I | re.M)
    if m:
        return int(m.group(1).replace(",", ""))
    # New format: county-prefixed; take the LAST occurrence (= cities section).
    last = None
    for mm in re.finditer(
        rf"^\s*[A-Za-z .]+?\s{{2,}}{re.escape(city)}\s+({_NUM})\b",
        text, re.I | re.M,
    ):
        last = mm
    return int(last.group(1).replace(",", "")) if last else None


def main() -> int:
    try:
        urls = scrape_report_urls()
    except Exception as e:  # noqa: BLE001
        print(f"! could not scrape index: {e}", file=sys.stderr)
        return 2
    print(f"Found {len(urls)} candidate report PDFs")

    rows: list[dict] = []
    failures: list[str] = []
    by_key: dict[tuple, int] = {}
    for url in urls:
        try:
            pdf = fetch_pdf_by_url(url)
            text = pdf_to_text(pdf)
        except Exception as e:  # noqa: BLE001
            failures.append(f"{url.rsplit('/', 1)[-1]}: fetch/convert failed ({e})")
            continue
        year = levy_year(text)
        if year is None:
            failures.append(f"{pdf.name}: could not read levy year from title page")
            continue
        if year < MIN_YEAR:
            continue
        for city in ("Detroit", "Flint"):
            tv = parse_city_tv(text, city)
            if tv is None:
                failures.append(f"{year}: no CITIES-section row for {city} ({pdf.name})")
                continue
            anchor = ANCHORS.get((city, year))
            if anchor is not None and tv != anchor:
                raise AssertionError(
                    f"PARSE MISMATCH {city} {year}: got {tv:,} but verified "
                    f"anchor is {anchor:,}. Refusing to emit bad data."
                )
            key = (city, year)
            if key in by_key:
                if by_key[key] != tv:
                    failures.append(
                        f"{city} {year}: conflicting values {by_key[key]:,} vs "
                        f"{tv:,} ({pdf.name}) — kept first")
                continue
            by_key[key] = tv
            rows.append({
                "city": city, "tax_year": year,
                "taxable_value": tv, "source_url": url.split("?")[0],
            })

    rows.sort(key=lambda r: (r["city"], r["tax_year"]))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["city", "tax_year", "taxable_value", "source_url"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows)} rows -> {OUT_CSV.relative_to(HERE)}")
    for city in ("Detroit", "Flint"):
        series = [(r["tax_year"], r["taxable_value"]) for r in rows if r["city"] == city]
        if not series:
            continue
        peak_yr, peak = max(series, key=lambda t: t[1])
        trough_yr, trough = min((t for t in series if t[0] >= peak_yr), key=lambda t: t[1], default=(None, None))
        latest_yr, latest = series[-1]
        print(f"\n{city}: {len(series)} yrs "
              f"[{series[0][0]}–{latest_yr}]")
        print(f"  peak   {peak_yr}: ${peak/1e9:6.3f}B")
        if trough_yr:
            print(f"  trough {trough_yr}: ${trough/1e9:6.3f}B  "
                  f"({100*(trough-peak)/peak:+.1f}% vs peak)")
        print(f"  latest {latest_yr}: ${latest/1e9:6.3f}B  "
              f"({100*(latest-peak)/peak:+.1f}% vs peak, "
              f"{100*latest/peak:.0f}% recovered, nominal)")

    if failures:
        print(f"\n{len(failures)} gaps (years missing from state site or unparsed):",
              file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
