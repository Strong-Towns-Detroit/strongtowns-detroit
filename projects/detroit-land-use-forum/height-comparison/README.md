# Height comparison

This exhibit audits Detroit BZA histories classified as height relief and
compares allowed with proposed height where both are explicitly stated in
feet.

The raw category contains 18 histories. Manual review found that `01-19` and
`1-19` describe the same 32 Monroe tower with the same 450-foot maximum and
535-foot proposal. The earlier unresolved appearance is collapsed, leaving 17
unique projects.

Ten projects state a complete pair. The remaining projects stay in the audit
CSV but outside the quantitative bars. Buildings, accessory structures, walls,
signs, and storage containers are identified separately rather than treated as
interchangeable objects.

Run:

```bash
python projects/detroit-land-use-forum/height-comparison/build_height_comparison_asset.py
```
