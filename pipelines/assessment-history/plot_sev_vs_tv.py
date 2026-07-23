"""The market-vs-taxable-base picture: SEV (market proxy) vs Taxable Value.

Two panels:

* DETROIT — SEV (ACFR Schedule 5) vs the canonical Form-625 tax-year TV, in
  dollars. The shaded band is assessed value untaxed under the Proposal A cap (it
  uncaps to SEV on sale). The story: by 2023 SEV is back *above* its nominal
  pre-crash peak (though still ~30% below the inflation-adjusted 2006 peak), while
  TV is stuck at ~54% of market.

* FLINT — real SEV (Genesee County Equalization) and Taxable Value (Treasury
  Form 625), each indexed to its own peak. Indexing sidesteps a basis mismatch
  (Flint SEV here is real-property-only; the Form-625 TV is real+personal), so we
  read *shape*, not the level ratio: both crater, the market falls a touch
  harder, and both recover slowly.

Output: output/sev_vs_tv.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
CSV = HERE / "data" / "sev_vs_tv.csv"
OUT = HERE / "output" / "sev_vs_tv.png"

SEV_C, TV_C = "#1f5c99", "#c1272d"


def main() -> int:
    df = pd.read_csv(CSV)
    fig, (axd, axf) = plt.subplots(1, 2, figsize=(15, 6.2))

    # ---- Panel A: Detroit, dollars ----
    d = df[df.city == "Detroit"].dropna(subset=["sev", "tv"]).sort_values("tax_year")
    yr, sev, tv = d.tax_year, d.sev / 1e9, d.tv / 1e9
    axd.fill_between(yr, tv, sev, color="#f0c419", alpha=0.30, zorder=1,
                     label="assessed value untaxed under the cap")
    axd.plot(yr, sev, "-o", ms=3.5, lw=2.2, color=SEV_C, zorder=3,
             label="SEV (market value ÷ 2)")
    axd.plot(yr, tv, "-o", ms=3.5, lw=2.2, color=TV_C, zorder=3,
             label="Taxable Value (what's taxed)")
    axd.annotate("2006 peak\n$14.1B", (2006, 14.11), fontsize=8, color=SEV_C,
                 xytext=(2, 6), textcoords="offset points", fontweight="bold")
    axd.annotate("market recovered: 2023 SEV $14.7B\n(nominal; ~30% below infl.-adj. 2006 peak)",
                 (2023, 14.74), fontsize=8.5, color=SEV_C, ha="right",
                 xytext=(-6, -4), textcoords="offset points", fontweight="bold")
    axd.annotate("…but taxable base only\n$8.0B = 54% of market",
                 (2023, 7.99), fontsize=8.5, color=TV_C, ha="right",
                 xytext=(-6, -22), textcoords="offset points", fontweight="bold")
    axd.annotate("SEV trough 2017\n$6.9B (−51% vs peak)", (2017, 6.87), fontsize=8,
                 color=SEV_C, xytext=(4, -26), textcoords="offset points")
    axd.set_title("Detroit (nominal): the market came back — the tax base didn't",
                  fontsize=11.5, fontweight="bold")
    axd.set_ylabel("$ billions"); axd.set_xlabel("Tax year")
    axd.set_ylim(0, 16); axd.grid(True, alpha=0.25)
    axd.legend(loc="lower left", fontsize=8.5, framealpha=0.9)

    # ---- Panel B: Flint, indexed to each series' own peak ----
    f = df[df.city == "Flint"].sort_values("tax_year")
    fs = f.dropna(subset=["sev"])
    ft = f.dropna(subset=["tv"])
    sev_peak = fs.sev.max()
    tv_peak = ft.tv.max()
    axf.plot(fs.tax_year, 100 * fs.sev / sev_peak, "-o", ms=3.5, lw=2.2,
             color=SEV_C, label="real SEV (market)")
    axf.plot(ft.tax_year, 100 * ft.tv / tv_peak, "-o", ms=3.5, lw=2.2,
             color=TV_C, label="Taxable Value")
    axf.axhline(100, color="#999", lw=0.8, ls=":")
    axf.annotate("real SEV: −62% to 2015 trough,\nstill −21% of peak in 2025",
                 (2015, 100 * 0.620 / (sev_peak / 1e9)), fontsize=8, color=SEV_C,
                 xytext=(6, 10), textcoords="offset points")
    axf.set_title("Flint: market fell harder (−62%) and has barely recovered",
                  fontsize=11.5, fontweight="bold")
    axf.set_ylabel("% of each series' own peak"); axf.set_xlabel("Tax year")
    axf.set_ylim(30, 108); axf.grid(True, alpha=0.25)
    axf.legend(loc="lower right", fontsize=9, framealpha=0.9)
    axf.text(0.03, 0.04,
             "Indexed to peak: Flint SEV is real-only, TV is real+personal —\n"
             "compare shapes, not the level ratio.",
             transform=axf.transAxes, fontsize=7.5, color="#555",
             bbox=dict(boxstyle="round,pad=0.3", fc="#f5f5f0", ec="#ccc"))

    fig.suptitle("Michigan Proposal A: State Equalized (market) Value vs Taxable Value",
                 fontsize=13, fontweight="bold", y=1.0)
    fig.text(0.5, -0.02,
             "Detroit: City ACFR Schedule 5 (AV=SEV & TV, citywide). "
             "Flint: Genesee County Equalization (real SEV) + MI Treasury Form 625 (TV). Tax years.",
             ha="center", fontsize=7.5, color="#888")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
