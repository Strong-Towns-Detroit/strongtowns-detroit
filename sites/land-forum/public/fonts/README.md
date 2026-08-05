# Bundled typefaces

Both families are licensed under the SIL Open Font License 1.1, which permits
redistribution and web embedding. The full licence text ships beside the fonts,
as the OFL requires.

| Files | Family | Copyright | Licence |
| --- | --- | --- | --- |
| `source-serif-4-*.woff2` | Source Serif 4 | © 2014–2023 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source' | `SourceSerif4-OFL.txt` |
| `inter-*.woff2` | Inter | © 2016–2024 The Inter Project Authors (https://github.com/rsms/inter) | `Inter-OFL.txt` |

Each family is a variable font split into `latin` and `latin-ext` subsets,
matching the split Google Fonts publishes. The matching `unicode-range` values
live in `app/fonts.css` — a subset file is useless without them, because the
browser would download every subset for every page.

Neither family may be redistributed under its reserved font name in modified
form. These files are unmodified subsets.
