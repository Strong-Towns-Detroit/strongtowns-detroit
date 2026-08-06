# Parking by project type

This exhibit groups all 62 parking-supply BZA histories into six mutually
exclusive primary project types. The crosswalk is manually reviewed and lives
in the build script so every classification is inspectable.

Mixed projects are assigned according to the dominant proposed use described
in the minutes. The aggregate required/proposed bars use only the 35 histories
where both figures are explicit; case counts use the full corpus.

Run:

```bash
python projects/detroit-land-use-forum/parking-by-project-type/build_parking_by_type_asset.py
```

Outputs include self-contained HTML, SVG, PNG, a case-level classification
audit, a category summary CSV, and summary JSON.
