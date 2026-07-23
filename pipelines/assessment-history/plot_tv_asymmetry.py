"""Plot the Proposal A recovery asymmetry for Flint and Detroit.

Reads data/ad_valorem_city_tv.csv (from fetch_ad_valorem.py) and renders each
city's total taxable value indexed to its own pre-crash peak (= 100), so the two
very differently-sized cities are directly comparable. A note gives the per-parcel
Proposal A recovery math (a 58% loss takes ~18 yrs even at the 5% ceiling). We do
NOT draw a 5%/yr "ceiling" line, because aggregate city TV legitimately outruns
the per-parcel cap through sales (which uncap parcels to SEV) and new construction.

Output: output/tv_asymmetry.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
CSV = HERE / "data" / "ad_valorem_city_tv.csv"
OUT = HERE / "output" / "tv_asymmetry.png"

CITY_COLOR = {"Flint": "#c1272d", "Detroit": "#1f5c99"}


def years_to_recover(drop_frac: float, rate: float) -> float:
    """Years for (1+rate)**n to climb back from (1-drop_frac) to 1.0."""
    import math
    return math.log(1.0 / (1.0 - drop_frac)) / math.log(1.0 + rate)


def main() -> int:
    df = pd.read_csv(CSV)
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for city, g in df.groupby("city"):
        g = g.sort_values("tax_year")
        peak_row = g.loc[g["taxable_value"].idxmax()]
        peak_year, peak_val = int(peak_row["tax_year"]), peak_row["taxable_value"]
        idx = 100.0 * g["taxable_value"] / peak_val
        color = CITY_COLOR.get(city, "#444")
        ax.plot(g["tax_year"], idx, "-o", ms=3.5, lw=2, color=color, label=city, zorder=3)

        # trough (post-peak minimum) and latest
        post = g[g["tax_year"] >= peak_year]
        tr = post.loc[post["taxable_value"].idxmin()]
        tr_year, tr_val = int(tr["tax_year"]), tr["taxable_value"]
        latest = g.iloc[-1]
        drop = 1.0 - tr_val / peak_val

        # annotate peak / trough / latest (stagger the two peak labels)
        peak_xy = (-64, 10) if city == "Flint" else (8, 24)
        ax.annotate(f"{city} peak {peak_year}: ${peak_val/1e9:.2f}B",
                    (peak_year, 100), textcoords="offset points", xytext=peak_xy,
                    fontsize=8, color=color, fontweight="bold")
        tr_xy = (-6, 16) if city == "Flint" else (4, -28)  # Flint up (legend is below-right)
        tr_ha = "right" if city == "Flint" else "left"
        ax.annotate(f"trough {tr_year}: {100*tr_val/peak_val:.0f}% of peak\n"
                    f"(-{drop*100:.0f}%)",
                    (tr_year, 100 * tr_val / peak_val), ha=tr_ha,
                    textcoords="offset points", xytext=tr_xy, fontsize=8, color=color)
        ax.annotate(f"{int(latest['tax_year'])}: {100*latest['taxable_value']/peak_val:.0f}%",
                    (latest["tax_year"], 100 * latest["taxable_value"] / peak_val),
                    textcoords="offset points", xytext=(6, -2), fontsize=8,
                    color=color, fontweight="bold")

    # per-parcel cap note
    n5 = years_to_recover(0.58, 0.05)
    n_infl = years_to_recover(0.58, 0.029)
    ax.axhline(100, color="#999", lw=0.8, ls=":")
    ax.text(0.015, 0.955, "pre-crash peak = 100", transform=ax.transAxes,
            fontsize=8, color="#666")
    ax.text(0.015, 0.03,
            "Per non-selling parcel the cap limits recovery to ≤5%/yr: a 58% loss needs\n"
            f"~{n5:.0f} yrs at the 5% ceiling, ~{n_infl:.0f} yrs at the ~2.9%/yr inflation cap "
            "actually applied.\n(City totals can outrun this via sales & new construction.)",
            transform=ax.transAxes, fontsize=8.5, color="#333",
            bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f0", ec="#ccc"))

    ax.set_title("Michigan Proposal A: taxable value crashes fast, recovers on a capped schedule\n"
                 "City total taxable value, indexed to each city's pre-crash peak",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Tax year")
    ax.set_ylabel("Taxable value (% of pre-crash peak)")
    ax.set_ylim(35, 112)
    ax.set_xlim(2003, 2026.5)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax.text(0.5, -0.13, "Source: Michigan Dept. of Treasury, Ad Valorem Property Tax Levy Report (Form 625), 1996–2025. "
            "City of Flint & City of Detroit (not townships).",
            transform=ax.transAxes, ha="center", fontsize=7.5, color="#888")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
