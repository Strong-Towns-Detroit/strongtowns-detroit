# BZA project-type enrichment

`classify_bza_project_types_with_gemini.py` classifies the physical project
behind each BZA case independently of Detroit’s legal relief categories.

The default pilot selects up to 12 cases whose normalized final outcome is
`denied_upheld`. It is intentionally cost-safe and resumable:

```bash
python pipelines/zoning/classify_bza_project_types_with_gemini.py --dry-run
python pipelines/zoning/classify_bza_project_types_with_gemini.py
```

After reviewing the per-case JSON and merged CSV:

```bash
python pipelines/zoning/classify_bza_project_types_with_gemini.py \
  --all \
  --workers 4
```

To study a wider definition of projects that did not proceed through the BZA
record, explicitly include dismissed or withdrawn cases:

```bash
python pipelines/zoning/classify_bza_project_types_with_gemini.py \
  --outcomes denied_upheld,dismissed_withdrawn \
  --all \
  --workers 4
```

## Interpretation

- `project_type_family` and `project_type_label` describe what was proposed,
  not the variance or appeal route.
- `proposal_language_tone` measures the tone of the supplied minutes. It is
  not a model judgment about whether the project is desirable.
- `intensity_direction` and `urban_form_orientation` are analytic attributes
  that can support later comparisons, but should be audited before publication.
- Evidence phrases make each classification reviewable against the extracted
  minutes.
