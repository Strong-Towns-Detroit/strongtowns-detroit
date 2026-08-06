"""Standalone HTML reviewer for exact Municode-backed legal-IR spans."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from typing import Any, Mapping

from .legal_ir import (
    LegalProvision,
    MunicodeSpan,
    ReviewedProvisionLedger,
    find_block,
    verify_provisions,
)


@dataclass(frozen=True)
class ReviewAtom:
    provision: LegalProvision
    span: MunicodeSpan
    source_ordinal: int

    @property
    def key(self) -> str:
        return f"{self.provision.id}#source-{self.source_ordinal + 1}"


def article_atoms(
    ledger: ReviewedProvisionLedger, document: str = "ARTICLE_I.municode.json"
) -> tuple[ReviewAtom, ...]:
    """Return exact source atoms in canonical source order."""
    atoms = [
        ReviewAtom(provision, span, ordinal)
        for provision in ledger.provisions
        for ordinal, span in enumerate(provision.sources)
        if span.document == document
    ]
    return tuple(sorted(atoms, key=lambda atom: (
        atom.span.source_index,
        -1 if atom.span.row is None else atom.span.row,
        -1 if atom.span.column is None else atom.span.column,
        atom.span.start,
        atom.span.end,
        atom.provision.id,
        atom.source_ordinal,
    )))


def render_review_page(
    corpus: Mapping[str, Any],
    ledger: ReviewedProvisionLedger,
    *,
    document: str = "ARTICLE_I.municode.json",
    selected: int | str = 0,
) -> str:
    """Render one selected atom and its full Municode-node context.

    All atoms are embedded in the standalone file. Previous/next controls and
    the URL hash switch between them without a server.
    """
    verify_provisions(corpus, ledger.provisions)
    atoms = article_atoms(ledger, document)
    if not atoms:
        raise ValueError(f"ledger has no source spans in {document}")
    selected_index = _selected_index(atoms, selected)
    panels = "".join(
        _render_atom(corpus, atom, index, len(atoms), index == selected_index)
        for index, atom in enumerate(atoms)
    )
    title = "Chapter 50 · Article I source-span review"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ --paper:#fbf7ee; --navy:#092849; --red:#cf3438; --ink:#16324f;
  --muted:#66758a; --line:#d8d3c8; --mark:#ffd25a; --card:#fffdf8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.55 Georgia,serif; }}
header {{ position:sticky; top:0; z-index:3; display:flex; align-items:center;
  justify-content:space-between; gap:24px; padding:18px 32px; color:white; background:var(--navy); }}
header h1 {{ margin:0; font-size:18px; letter-spacing:.02em; }}
.nav {{ display:flex; align-items:center; gap:10px; font:600 13px/1.2 Arial,sans-serif; }}
button {{ border:1px solid #ffffff70; border-radius:3px; padding:8px 12px;
  color:white; background:transparent; cursor:pointer; }}
button:disabled {{ opacity:.35; cursor:default; }}
main {{ max-width:1180px; margin:0 auto; padding:34px; }}
.atom {{ display:none; }} .atom.active {{ display:block; }}
.eyebrow,.status,.source-id,.label {{ font-family:Arial,sans-serif; }}
.eyebrow {{ color:var(--red); font-size:12px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
h2 {{ margin:8px 0 4px; color:var(--navy); font-size:34px; line-height:1.15; }}
.source-id {{ color:var(--muted); font-size:12px; overflow-wrap:anywhere; }}
.grid {{ display:grid; grid-template-columns:minmax(0,2fr) minmax(280px,1fr); gap:28px; margin-top:26px; }}
.card {{ padding:22px; border:1px solid var(--line); background:var(--card); }}
.context-block {{ margin:0 0 13px; padding:12px 14px; border-left:3px solid transparent; white-space:pre-wrap; }}
.context-block.selected {{ border-left-color:var(--red); background:#f7efe3; }}
mark {{ padding:.05em .12em; color:#201a09; background:var(--mark); box-shadow:0 0 0 2px var(--mark); }}
table {{ width:100%; border-collapse:collapse; font:14px/1.35 Arial,sans-serif; }}
td {{ padding:7px; border:1px solid var(--line); vertical-align:top; }}
td.selected-cell {{ outline:3px solid var(--red); outline-offset:-3px; }}
.status {{ display:inline-block; margin:8px 0 18px; padding:5px 8px; border-radius:2px;
  color:white; background:var(--red); font-size:12px; font-weight:700; text-transform:uppercase; }}
dl {{ margin:0; }} dt {{ margin-top:15px; color:var(--muted); font:700 11px Arial,sans-serif;
  letter-spacing:.08em; text-transform:uppercase; }} dd {{ margin:4px 0 0; }}
pre {{ overflow:auto; margin:5px 0 0; padding:10px; background:#f1eee7; font:12px/1.45 monospace; white-space:pre-wrap; }}
.quote {{ font-size:20px; line-height:1.45; }}
@media (max-width:800px) {{ header {{ align-items:flex-start; flex-direction:column; }}
  main {{ padding:22px 16px; }} .grid {{ grid-template-columns:1fr; }} h2 {{ font-size:27px; }} }}
</style>
</head>
<body>
<header><h1>{escape(title)}</h1><div class="nav"><button id="previous">← Previous</button>
<span id="position"></span><button id="next">Next →</button></div></header>
<main>{panels}</main>
<script>
const panels=[...document.querySelectorAll('.atom')];
let index=Math.max(0,panels.findIndex(p=>p.classList.contains('active')));
function show(next,writeHash=true){{
  index=Math.max(0,Math.min(panels.length-1,next));
  panels.forEach((p,i)=>p.classList.toggle('active',i===index));
  document.getElementById('position').textContent=`${{index+1}} of ${{panels.length}}`;
  document.getElementById('previous').disabled=index===0;
  document.getElementById('next').disabled=index===panels.length-1;
  if(writeHash) history.replaceState(null,'','#'+panels[index].id);
}}
function fromHash(){{ const hit=panels.findIndex(p=>p.id===location.hash.slice(1)); if(hit>=0) show(hit,false); }}
document.getElementById('previous').onclick=()=>show(index-1);
document.getElementById('next').onclick=()=>show(index+1);
document.addEventListener('keydown',e=>{{ if(e.key==='ArrowLeft')show(index-1); if(e.key==='ArrowRight')show(index+1); }});
window.addEventListener('hashchange',fromHash); fromHash(); show(index,false);
</script>
</body></html>"""


def _selected_index(atoms: tuple[ReviewAtom, ...], selected: int | str) -> int:
    if isinstance(selected, int):
        if selected < 0 or selected >= len(atoms):
            raise IndexError(f"selected atom {selected} outside 0..{len(atoms)-1}")
        return selected
    for index, atom in enumerate(atoms):
        if atom.key == selected or atom.provision.id == selected:
            return index
    raise KeyError(f"unknown review atom {selected!r}")


def _render_atom(
    corpus: Mapping[str, Any], atom: ReviewAtom, index: int, total: int, active: bool
) -> str:
    provision, span = atom.provision, atom.span
    block = find_block(corpus, span)
    document = next(item for item in corpus["documents"] if item["document"] == span.document)
    node_blocks = [item for item in document["blocks"] if item.get("municodeNodeId") == span.node_id]
    context = "".join(_render_context_block(item, span) for item in node_blocks)
    status = str(provision.review.get("status", "unreviewed"))
    disposition = str(provision.review.get("disposition", status))
    section = span.section or "Unnumbered Article I material"
    element_id = _html_id(atom.key)
    return f"""<article class="atom{' active' if active else ''}" id="{element_id}">
<div class="eyebrow">Source atom {index + 1} of {total} · {escape(section)}</div>
<h2>{escape(provision.id)}</h2>
<div class="source-id">{escape(atom.key)} · node {escape(str(span.node_id))} · block {span.source_index}</div>
<div class="grid"><section class="card"><div class="label">SURROUNDING MUNICODE NODE</div>{context}</section>
<aside class="card"><span class="status">{escape(status)}</span><dl>
<dt>Disposition</dt><dd>{escape(disposition)}</dd>
<dt>Exact selected text</dt><dd class="quote">“{escape(span.quote)}”</dd>
<dt>Subject</dt><dd><pre>{_json(provision.subject)}</pre></dd>
<dt>Effect</dt><dd><pre>{_json(provision.effect)}</pre></dd>
<dt>Conditions</dt><dd><pre>{_json(provision.conditions)}</pre></dd>
<dt>Exceptions</dt><dd><pre>{_json(provision.exceptions)}</pre></dd>
<dt>Cross-references</dt><dd><pre>{_json(provision.cross_references)}</pre></dd>
<dt>Span digest</dt><dd class="source-id">{escape(span.sha256)}</dd>
</dl></aside></div></article>"""


def _render_context_block(block: Mapping[str, Any], selected: MunicodeSpan) -> str:
    is_selected = block.get("sourceIndex") == selected.source_index
    class_name = "context-block selected" if is_selected else "context-block"
    if block.get("type") == "paragraph":
        text = str(block.get("text", ""))
        content = _highlight(text, selected) if is_selected else escape(text)
        return f'<p class="{class_name}">{content}</p>'
    if block.get("type") == "table":
        rows = []
        for row_index, row in enumerate(block.get("rows", [])):
            cells = []
            for column_index, value in enumerate(row):
                chosen = is_selected and row_index == selected.row and column_index == selected.column
                content = _highlight(str(value), selected) if chosen else escape(str(value))
                cells.append(f'<td class="{"selected-cell" if chosen else ""}">{content}</td>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return f'<div class="{class_name}"><table>{"".join(rows)}</table></div>'
    return ""


def _highlight(text: str, span: MunicodeSpan) -> str:
    return (
        escape(text[:span.start]) + "<mark>" + escape(text[span.start:span.end])
        + "</mark>" + escape(text[span.end:])
    )


def _json(value: Any) -> str:
    return escape(json.dumps(value, indent=2, sort_keys=True))


def _html_id(value: str) -> str:
    return "atom-" + "".join(character if character.isalnum() else "-" for character in value)
