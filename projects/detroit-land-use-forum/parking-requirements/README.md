# Parking-requirements exhibit

This exhibit compares the number of off-street parking spaces stated as
required in Detroit Board of Zoning Appeals minutes with the number the
applicant proposed or already provided.

The unit is one deduplicated BZA case history. A case enters the numeric
comparison only when the minutes explicitly state both figures. Cases that say
only “deficient parking,” or state only the requirement or deficiency, remain
in `parking-case-audit.csv` with `numeric_status=not_stated`.

Run:

```bash
python projects/detroit-land-use-forum/parking-requirements/build_parking_requirements_asset.py
```

Outputs under `output/`:

- self-contained HTML;
- SVG;
- PNG when `rsvg-convert` is available;
- a complete case-level audit CSV; and
- a machine-readable summary.

The small transcription table in the build script is intentional. It keeps
every published number reviewable against the representative minutes text and
documents cases with transit, employee, or multi-use adjustments.
