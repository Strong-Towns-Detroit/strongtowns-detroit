# Source-to-compiler review tool

Static review application for the reviewed zoning-language corpus. It presents
each rule as exact legal text, authored ZDL, and normalized compiler output.

Build the bundle:

```bash
python review-tool/build_data.py
```

Serve the repository root and open `review-tool/`, for example:

```bash
python -m http.server 8766
```

## Anchored comments

- Click a line number to add that line to a comment draft. Shift-click another
  line number to extend the custom line selection.
- Drag across rendered words to create a custom contiguous token highlight,
  including ranges spanning multiple lines. Native system selection is not
  used.
- Add further selections from any representation before submitting. One
  comment may therefore reference legal text, authored syntax, and compiled
  output together.
- Anchor markers remain on the selected lines, while draft and submitted
  comments render in a dedicated rail outside every review window. The rail
  reserves its own desktop space and never covers or intercepts the selected
  passage. A cross-window comment therefore has one readable body and links
  back to all of its selected representations.
- Submitted comments and unfinished drafts autosave in browser local storage
  and may be exported or imported as JSON.

Each comment is bound to the immutable artifact version visible when it was
submitted. `build_data.py` fingerprints the legal text, presented rule, complete
ontology, and compiled output together. A changed fingerprint appends a new
snapshot to `versions.json`; it never overwrites the prior snapshot. The
Artifact version selector can therefore reopen the old text and its comments
after a revision. Pre-versioning comments migrate to the initial `v1` baseline.

Comments are threaded. Reviewer replies autosave with the browser review state.
Repository-backed Codex replies live in `replies.json`, keyed by comment ID, so
they can be rebuilt into the review bundle and displayed alongside reviewer
follow-ups without rewriting the original comment.

Anchors store pane identity, line range, word-token range, and an exact quote.
The word-token range supplies precise highlighting; the quote and line range
support later migration and review if rendering changes.

Syntax highlighting is representation-aware: legal citations and operative
modals are distinguished in source text; ZDL keywords, concepts, relations,
strings, literals, and numbers receive semantic colors; compiled JSON separates
properties, values, literals, and punctuation. Highlighting is layered onto the
existing word tokens so it does not reduce comment-selection precision.

Legal text, Presented rule, Compiled form, Ontology, and text wrapping are
independently toggleable. Each module's complete ontology is persisted as an
independent `examples/ontologies/*.ontology.zdl` source file and displayed without
rule-specific slicing.
Rule navigation, window visibility, wrapping, layout reset, review import/export,
and comments live in one persistent sidebar. The sidebar is collapsible, and its
state autosaves with the workspace.
The four representation windows can be reordered by dragging their headers.
Drop on the top or bottom half of another window to insert within that window's
column. Drop on its left or right half to create an adjacent column. Vertical
gutters resize whole columns; each column has independent horizontal gutters
for its own rows. The default layout gives the legal-source column less width.
Window layout and display preferences autosave with the review.
