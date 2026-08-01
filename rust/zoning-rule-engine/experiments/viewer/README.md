# DSL review viewer

Build the self-contained source and test bundle, then serve the directory:

```sh
python build_data.py
python -m http.server 8765
```

Open <http://localhost:8765>. Rankings, scores, and notes remain in browser
local storage. Export produces a JSON review that can be committed or shared.

The builder runs each experiment's Rust tests and embeds their named results
alongside all six authored source alternatives. The viewer deliberately scores
ontology and legal-rule syntax on separate axes.
