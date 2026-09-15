# Land Forum BZA launch

Implementation brief, September 15, 2026. Target: September 19–20.

- Public scope: BZA home, atlas, methods, and a secondary chart studio.
- Brand: Land Forum, a project of Strong Towns Detroit.
- Baseline: existing relief-request map; size represents hearings per case.
- Every exported graphic uses whole Detroit. Interactive zoom and pan never
  determine the exported geography. Neighborhood and drawn boundaries come later.
- Case filters carry into the export and never reposition remaining symbols.
- Create graphic opens a modal with a 500 ms map transition, editable headline
  and explanation, and automatic legend, coverage, sources, and branding.
- Preview and downloaded 1080 × 1350 PNG use the same SVG renderer.
- BZA 1.1.0: 417 cases, 509 hearings, 408 mapped; unmatched records remain usable.
- Saved links retain immutable map and case bundles. Historical chart recipes
  remain supported.

See README.md for preparation, verification, publishing, and deployment commands.
Launch gates: passing production browser tests, visually checked exports, a real
public origin, authenticated Cloudflare deployment, and live smoke checks. The
local implementation does not itself announce the launch or post to Instagram.
