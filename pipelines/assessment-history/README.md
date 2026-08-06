# assessment-history

Quantifies the Michigan **Proposal A** taxable-value recovery asymmetry ("value
falls fast, but can only climb back ≤5%/yr") for Detroit and Flint, from
authoritative state data.

This is the first data-collection step toward simulating **land-value-tax and
assessment-strategy policy** on real metro-Detroit parcels: the same
SEV / Taxable-Value / market-value divergence modeled here is the assessment
dynamic the market simulation needs to reproduce.

## Contents

| File | What |
|---|---|
| `fetch_ad_valorem.py` | Scrapes the MI Treasury Ad Valorem Levy (Form 625) index, downloads each year's PDF (1996–2025), and parses **City of Detroit** and **City of Flint** total taxable value. Emits `data/ad_valorem_city_tv.csv`. |
| `plot_tv_asymmetry.py` | Renders `output/tv_asymmetry.png` — taxable value indexed to each city's pre-crash peak, with a note on the per-parcel 5%/yr cap recovery math (no ceiling line is drawn, since aggregate TV outruns the per-parcel cap via sales & new construction). |
| `plot_sev_vs_tv.py` | Renders `output/sev_vs_tv.png` — SEV (market proxy) vs Taxable Value. Reads `data/sev_vs_tv.csv`. Detroit panel (dollars; ACFR SEV vs canonical Form-625 TV) shows the market recovering above its *nominal* 2006 peak while TV stays at 54% of it; Flint panel (indexed to peak) shows the deeper −62% market drop. |
| `BRIEF_property_tax_asymmetry.md` | Shareable write-up answering the originating question. |

`data/sev_vs_tv.csv` — City of Detroit SEV+TV (from ACFR Schedule 5, cross-validated across three editions) and City of Flint real SEV (Genesee County Equalization) aligned with Form-625 TV. **Basis caveat:** Detroit SEV & TV are both citywide real+personal from one source (clean ratio); Flint SEV is real-only while its Form-625 TV is real+personal — compare Flint by *shape*, not level ratio. Detroit SEV for 2024–25 and a real-only Flint TV series need the eequal portal (forms 4023/4046).

## Run

```bash
python fetch_ad_valorem.py   # needs `pdftotext` (poppler) on PATH; caches PDFs under data/pdf/
python plot_tv_asymmetry.py  # needs matplotlib + pandas
```

## Provenance & gotchas (read before extending)

- **Source:** Michigan Dept. of Treasury, *Ad Valorem Property Tax Levy Report*
  (STC Form 625). `michigan.gov` returns HTTP 403 to default user-agents — the
  fetcher sends a browser UA.
- **City ≠ Township.** Genesee County has both a City of Flint and a Flint
  (Charter) Township of similar size. The parser disambiguates by row layout
  (pre-2016 city rows are column-0 left-aligned; 2019+ rows are county-prefixed
  with cities after townships) and **asserts every parse against hand-verified
  anchors** in `ANCHORS`. A mislabel raises rather than emitting bad data.
- **Scope:** canonical series is **2004–2025** (`MIN_YEAR`). Pre-2004 reports use
  an older layout this parser mis-reads; extending earlier needs its own anchors.
- **This is taxable value, not SEV.** Market/SEV fell harder than TV in the
  crash. The matching SEV-by-class series lives in Treasury's "eequal" portal
  (forms 4023/4046, 2008–present) and is the next pull.
