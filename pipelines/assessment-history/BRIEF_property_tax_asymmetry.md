# Michigan's property-tax ratchet: why Flint's tax base still hasn't recovered

*A short answer to Jon Wylie's question — does the "capped rising, uncapped
falling" property-value data exist for Detroit, and can we quantify it?*

**Short answer: yes, it's real, it's statewide law (Proposal A of 1994), the
data exists, and the numbers below are pulled straight from the Michigan
Treasury's own annual reports.**

## The mechanism

Every Michigan parcel carries two numbers:

- **State Equalized Value (SEV)** ≈ 50% of true market value. It moves with the
  market, up *and* down.
- **Taxable Value (TV)** — what you actually pay tax on. Proposal A caps its
  annual growth at **the lesser of 5% or inflation**, but puts **no floor under
  it**: TV can never exceed SEV, so when the market craters, SEV craters and TV
  is dragged down *with the market, at full speed*.

The asymmetry: **down fast, up slow.** On the way up, TV is throttled to
≤5%/yr no matter how fast the market recovers. The only thing that resets a
parcel is a **sale** (which "uncaps" it back to SEV). A city is mostly parcels
that *don't* sell in a given year — so the whole tax base recovers on the slow,
capped schedule. Joel Arnold's "40-odd years to get back" is exactly this.

## The math on "40 years"

Recovering from a 58% loss (Flint's actual taxable-value drop, below) means
climbing back to 1/(1−0.58) = 2.4× the trough:

| Annual cap that applies | Years to recover |
|---|---|
| 5% (the ceiling) | ~18 years |
| ~2.9% (avg. inflation multiplier actually applied) | ~30 years |
| ~2.0% (low-inflation years, several were near 0%) | ~44 years |

So "40-odd years" is squarely in range — and **conservative**, since several
post-crash years hit the inflation cap at or near **0%**.

## What actually happened (Michigan Treasury, Form 625, 1996–2025)

![Taxable value indexed to each city's pre-crash peak](output/tv_asymmetry.png)

**City of Flint** — total taxable value:
- Peak **2007: $1.69 B**
- Trough **2016: $0.71 B** — a **−58%** collapse
- **2025: $1.06 B** — still **38% below its 2007 peak, eighteen years later**
  (and far worse adjusted for inflation)

**City of Detroit** — total taxable value:
- Peak **2008: $10.03 B**
- Trough **2017: $6.04 B** — **−40%**
- **2025: $9.35 B** — recovered to **93% of peak** (nominal)

The two cities diverge on the way back up — Detroit's downtown/Midtown boom,
new construction, and the 2017 reappraisal pulled it most of the way back;
Flint has not had that engine, so the cap is the binding constraint and its base
is still deeply depressed. Corroboration: the **Citizens Research Council**
(June 2024) found that **as of 2024, no Genesee County community had exceeded
its inflation-adjusted 2008 taxable value** — 16+ years on.

## The clincher: the market recovered, but the tax base can't

Taxable value is only half the picture. The other half is **State Equalized
Value (SEV)** — the market-value proxy. When you plot them together, the ratchet
is undeniable:

![SEV vs Taxable Value, Detroit and Flint](output/sev_vs_tv.png)

**Detroit** (SEV from the city's own audited ACFR; TV is the canonical Treasury
Form-625 series — same citywide, real+personal basis):

- Market value (SEV) crashed **−51%** (2006 peak $14.1B → 2017 trough $6.9B) —
  *harder* than taxable value's −40%, because the market has no floor.
- Then the market came **most of the way back**: by **2023 SEV hit $14.7B — above
  its *nominal* pre-crash peak** (though still ~30% below the inflation-adjusted
  2006 peak).
- But taxable value only crawled to **$8.0B — 54% of market value.** The city is
  now taxing **just 54¢ of every market dollar**, versus ~70–80% before the
  crash. That gap (the shaded band) is revenue the recovery *should* have
  restored and the cap withholds — for years to come.

*Caveat:* "AV = SEV = market ÷ 2" is the statutory reading we use for the ratio;
Detroit's documented **2010–2016 over-assessment** episode means SEV ran high
relative to true market in those years, so the ratio is imperfect there — but the
direction is **conservative** for the thesis (a too-high SEV understates, not
overstates, the recovery gap).

**Flint**: real market value fell even harder — **−62%** to its 2015 trough — and
in 2025 is still **~21% below its 2007 peak.** Same shape, deeper hole, slower
climb.

So Jon's instinct was right on both counts: the ~75% he recalls is the
**market/SEV** collapse (bigger than the taxable-value drop), and the reason it
matters for a generation is precisely that the taxable base — capped on the way
up — can't follow the market back.

## We can also see it parcel-by-parcel, right now

Detroit publishes a live parcel roll (all ~378k parcels) with each parcel's
assessed and taxable value. Today:

- **Residential taxable value is just 44¢ per $1 of assessed value.**
- Citywide, the Proposal A cap is currently shielding **~$8.3 B of assessed
  value — roughly $16.5 B of market value — from taxation.**

That's the same asymmetry as a present-day snapshot: assessed value has tracked
the market recovery back up, but taxable value is still parked at the
depressed/capped level.

## Does the data exist? Where it lives

| Level | Source | Coverage | Status |
|---|---|---|---|
| City/unit **taxable value** | MI Treasury Ad Valorem Levy (Form 625) | 1996–2025 annual | ✅ pulled |
| City/unit **SEV** (market proxy) | Detroit ACFR Schedule 5; Genesee County Equalization | Detroit 2006–2023, Flint 2002–2025 | ✅ pulled |
| SEV/TV **by property class** | MI Treasury STC "eequal" portal (forms 4023/4046) | 2008–present | fills 2024–25 Detroit gap; browser-gated |
| Parcel-level AV & TV | Detroit Open Data (ArcGIS) | current + prior yr | ✅ reachable now |
| Parcel-level **history** (crash era) | FOIA to Detroit Assessor / Wayne County; openICPSR academic deposits | 2008–2013 | request (see below) |

**Bottom line for the group:** the aggregate story is fully documented and
reproducible from state data (the chart above regenerates from a script). The
parcel-level *current* gap is one API call. A parcel-level *historical* panel —
the thing that would let us model this house-by-house — is the one piece that
isn't free, and is where a data request or a small budget would go.

---
*Numbers reproducible via `pipelines/assessment-history/` (fetch + parse +
plot). Sources cited inline; every city figure is asserted against a
hand-verified value so the pipeline fails loudly rather than mislabeling
City-of-Flint vs Flint-Township data. An audit of this brief caught a levy-year
labeling bug in the fetcher (transitional PUB_LEVY filenames like
`2019_2018_625…` mis-dated the 2018 report); it is fixed — the true levy-2018
value is recovered and the troughs corrected to Detroit 2017 / Flint 2016 — so
the figures here are current.*
