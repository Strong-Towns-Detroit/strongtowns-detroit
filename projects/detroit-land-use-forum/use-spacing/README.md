# Use-spacing threshold exhibit

This exhibit compares the actual separation stated in Detroit Board of Zoning
Appeals minutes with the applicable required separation.

For a case with multiple conflicts, the plotted pair is the one with the
smallest `actual distance / required distance` ratio. The complete proposal
text, selected rule context, nearby-use description, outcome, and both
distances remain in the audit CSV.

Run:

```bash
python projects/detroit-land-use-forum/use-spacing/build_use_spacing_asset.py
```

The source classifier returned 45 histories. Manual review identified one
false positive: case 12-19 concerns parking and a neighborhood-petition radius,
not a use-spacing request. Of the 44 verified spacing histories, 37 state an
explicit required and actual distance pair.

Outputs under `output/`:

- self-contained HTML with case details on hover;
- SVG;
- PNG when `rsvg-convert` is available;
- complete case-level audit CSV; and
- summary JSON.
