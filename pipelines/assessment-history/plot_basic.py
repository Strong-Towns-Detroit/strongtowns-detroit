"""Basic, unembellished views straight from the assessment CSVs.

Four raw panels — no narrative annotations, just the data as pulled:
  1. Detroit total taxable value ($B) over time
  2. Flint total taxable value ($M) over time
  3. Detroit SEV vs Taxable Value ($B)
  4. Taxable value as % of SEV, both cities

Reads data/ad_valorem_city_tv.csv and data/sev_vs_tv.csv.
Output: output/assessment_basic.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
TV_CSV = HERE / "data" / "ad_valorem_city_tv.csv"
SEV_CSV = HERE / "data" / "sev_vs_tv.csv"
OUT = HERE / "output" / "assessment_basic.png"

BLUE, RED = "#1f5c99", "#c1272d"


def main() -> int:
    tv = pd.read_csv(TV_CSV)
    sev = pd.read_csv(SEV_CSV)
    det_tv = tv[tv.city == "Detroit"].sort_values("tax_year")
    fli_tv = tv[tv.city == "Flint"].sort_values("tax_year")
    det = sev[sev.city == "Detroit"].dropna(subset=["sev", "tv"]).sort_values("tax_year")
    fli = sev[sev.city == "Flint"].dropna(subset=["sev", "tv"]).sort_values("tax_year")

    fig, ax = plt.subplots(2, 2, figsize=(13, 8))

    # 1. Detroit TV ($B)
    ax[0, 0].plot(det_tv.tax_year, det_tv.taxable_value / 1e9, "-o", ms=3, color=BLUE)
    ax[0, 0].set_title("Detroit — total taxable value")
    ax[0, 0].set_ylabel("$ billions")

    # 2. Flint TV ($M)
    ax[0, 1].plot(fli_tv.tax_year, fli_tv.taxable_value / 1e6, "-o", ms=3, color=RED)
    ax[0, 1].set_title("Flint — total taxable value")
    ax[0, 1].set_ylabel("$ millions")

    # 3. Detroit SEV vs TV ($B)
    ax[1, 0].plot(det.tax_year, det.sev / 1e9, "-o", ms=3, color=BLUE, label="SEV (assessed)")
    ax[1, 0].plot(det.tax_year, det.tv / 1e9, "-o", ms=3, color=RED, label="Taxable Value")
    ax[1, 0].set_title("Detroit — SEV vs Taxable Value")
    ax[1, 0].set_ylabel("$ billions")
    ax[1, 0].legend(fontsize=8)

    # 4. TV as % of SEV, both cities
    ax[1, 1].plot(det.tax_year, 100 * det.tv / det.sev, "-o", ms=3, color=BLUE, label="Detroit")
    ax[1, 1].plot(fli.tax_year, 100 * fli.tv / fli.sev, "-o", ms=3, color=RED,
                  label="Flint (real-only SEV — basis differs)")
    ax[1, 1].set_title("Taxable value as % of SEV")
    ax[1, 1].set_ylabel("% of SEV")
    ax[1, 1].legend(fontsize=8)

    for a in ax.flat:
        a.grid(True, alpha=0.25)
        a.set_xlabel("Tax year")

    fig.suptitle("Detroit & Flint assessment data — raw views (MI Treasury Form 625; "
                 "Detroit ACFR + Genesee County SEV)", fontsize=12, fontweight="bold")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
