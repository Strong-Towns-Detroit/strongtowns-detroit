const data = window.LEGAL_REVIEW_DATA;
const columnOrder = ["text", "presented", "ontology", "compiled"];
const defaultPreferences = {
  visiblePanes: [...columnOrder],
  paneColumns: [["text", "ontology"], ["presented", "compiled"]],
  columnWeights: [0.72, 1.28],
  paneHeights: { text: 1, presented: 1, ontology: 1, compiled: 1 },
  wrap: false,
  sidebarCollapsed: false,
};
const storageKey = "zoning-language-review-v1";

let state = loadState();
let ruleIndex = 0;
let versionSelections = {};
let activeComment = null;
let openCommentId = null;
let drag = null;
let previewAnchor = null;
const lineStarts = {};

function loadState() {
  try {
    const loaded = JSON.parse(localStorage.getItem(storageKey)) || {};
    const preferences = { ...defaultPreferences, ...(loaded.preferences || {}) };
    if (loaded.preferences?.ontology === false) preferences.visiblePanes = preferences.visiblePanes.filter(pane => pane !== "ontology");
    else if (!preferences.visiblePanes.includes("ontology")) preferences.visiblePanes.push("ontology");
    preferences.visiblePanes = preferences.visiblePanes.filter(pane => columnOrder.includes(pane));
    if (!loaded.preferences?.paneColumns) {
      const legacyRows = loaded.preferences?.paneRows || [loaded.preferences?.paneOrder || ["text", "presented", "compiled"]];
      const legacyPanes = legacyRows.flat().filter(pane => columnOrder.includes(pane));
      for (const pane of columnOrder) if (!legacyPanes.includes(pane)) legacyPanes.push(pane);
      preferences.paneColumns = [legacyPanes.slice(0, 2), legacyPanes.slice(2)];
    }
    preferences.paneColumns = preferences.paneColumns.map(column => column.filter(pane => columnOrder.includes(pane))).filter(column => column.length);
    const placed = new Set(preferences.paneColumns.flat());
    for (const pane of columnOrder) if (!placed.has(pane)) preferences.paneColumns.at(-1).push(pane);
    preferences.columnWeights = preferences.paneColumns.map((_, index) => preferences.columnWeights?.[index] || 1);
    preferences.paneHeights = { ...defaultPreferences.paneHeights, ...(preferences.paneHeights || {}) };
    const drafts = {};
    for (const [ruleId, draft] of Object.entries(loaded.drafts || {})) {
      drafts[ruleId] = {
        body: typeof draft?.body === "string" ? draft.body : "",
        anchors: Array.isArray(draft?.anchors) ? draft.anchors.map(normalizeAnchor).filter(Boolean) : [],
      };
    }
    const comments = Array.isArray(loaded.comments) ? loaded.comments.map(comment => ({
      ...comment,
      body: typeof comment?.body === "string" ? comment.body : "",
      anchors: Array.isArray(comment?.anchors) ? comment.anchors.map(normalizeAnchor).filter(Boolean) : [],
      versionId: comment.versionId || baselineVersionForRule(comment.ruleId),
      replies: Array.isArray(comment.replies) ? comment.replies : [],
    })) : [];
    return {
      comments,
      drafts,
      preferences,
    };
  } catch {
    return { comments: [], drafts: {}, preferences: structuredClone(defaultPreferences) };
  }
}

function normalizeAnchor(anchor) {
  if (!anchor || !columnOrder.includes(anchor.pane)) return null;
  const startLine = Number.isFinite(Number(anchor.startLine)) ? Number(anchor.startLine) : 0;
  const endLine = Number.isFinite(Number(anchor.endLine)) ? Number(anchor.endLine) : startLine;
  return {
    ...anchor,
    kind: anchor.kind === "lines" ? "lines" : "words",
    startLine: Math.max(0, startLine),
    endLine: Math.max(startLine, endLine),
    startToken: Number.isFinite(Number(anchor.startToken)) ? Number(anchor.startToken) : -1,
    endToken: Number.isFinite(Number(anchor.endToken)) ? Number(anchor.endToken) : -1,
    quote: typeof anchor.quote === "string" ? anchor.quote : "",
  };
}

function saveState() { localStorage.setItem(storageKey, JSON.stringify(state)); }
function currentRuleFamily() { return data.rules[ruleIndex]; }
function versionsForRule(rule = currentRuleFamily()) { return rule.versions?.length ? rule.versions : [{ ...rule, versionId: "v1" }]; }
function baselineVersionForRule(ruleId) { return versionsForRule(data.rules.find(rule => rule.id === ruleId) || { versions: [] })[0]?.versionId || "v1"; }
function currentRule() {
  const family = currentRuleFamily();
  const versions = versionsForRule(family);
  const selected = versionSelections[family.id] || family.currentVersion || versions.at(-1).versionId;
  return versions.find(version => version.versionId === selected) || versions.at(-1);
}
function reviewKey() { return `${currentRule().id}@${currentRule().versionId || "v1"}`; }
function currentDraft() {
  return state.drafts[reviewKey()] || state.drafts[currentRule().id] || { anchors: [], body: "" };
}
function updateDraft(next) {
  state.drafts[reviewKey()] = next;
  delete state.drafts[currentRule().id];
  saveState();
}

function paneData(pane) {
  if (pane === "ontology") return currentRule().panes.presented.ontology;
  return currentRule().panes[pane];
}

function tokenizeLine(text, language = "text") {
  const items = tokenizePlainLine(text);
  if (language === "json") classifyJson(items, text);
  else if (language === "zdl") classifyZdl(items);
  else classifyLegalText(items);
  return items;
}

function tokenizePlainLine(text) {
  const items = [];
  const expression = /[\p{L}\p{N}_§.-]+|[^\s]/gu;
  let cursor = 0;
  for (const match of text.matchAll(expression)) {
    if (match.index > cursor) items.push({ space: text.slice(cursor, match.index) });
    items.push({ word: match[0] });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) items.push({ space: text.slice(cursor) });
  return items;
}

function classifyJson(items, text) {
  const propertyString = /^\s*"(?:\\.|[^"\\])*"\s*:/.test(text);
  let inString = false;
  for (const item of items) {
    if (item.word === undefined) continue;
    if (item.word === '"') { item.type = propertyString ? "property" : "string"; inString = !inString; continue; }
    if (inString) { item.type = propertyString ? "property" : "string"; continue; }
    if (/^-?\d/.test(item.word)) item.type = "number";
    else if (/^(true|false|null)$/.test(item.word)) item.type = "literal";
    else item.type = "punctuation";
  }
}

function classifyZdl(items) {
  const keywords = new Set(["action", "as", "concept", "defeasible", "duty", "else", "exception", "extends", "given", "if", "individual", "interpretive", "must", "ontology", "otherwise", "phrase", "relation", "require", "resolution", "rule", "source", "then", "unless", "when"]);
  const literals = new Set(["true", "false", "open", "resolved", "strict"]);
  let inString = false;
  items.forEach((item, index) => {
    if (item.word === undefined) return;
    if (item.word === '"') { item.type = "string"; inString = !inString; return; }
    if (inString) { item.type = "string"; return; }
    const value = item.word;
    const nextWord = items.slice(index + 1).find(candidate => candidate.word !== undefined)?.word;
    if (keywords.has(value)) item.type = "keyword";
    else if (literals.has(value)) item.type = "literal";
    else if (/^§/.test(value)) item.type = "citation";
    else if (/^\d/.test(value)) item.type = "number";
    else if (/^[A-Z][\p{L}\p{N}_]*$/u.test(value)) item.type = "type";
    else if (nextWord === "(" && /^[a-z_]/.test(value)) item.type = "relation";
    else if (/^[{}()[\],:=>!&|]+$/.test(value)) item.type = "punctuation";
  });
}

function classifyLegalText(items) {
  const modal = new Set(["shall", "must", "may", "unless", "except", "notwithstanding", "required", "prohibited"]);
  for (const item of items) {
    if (item.word === undefined) continue;
    const normalized = item.word.toLowerCase().replace(/[^a-z]/g, "");
    if (/^§/.test(item.word)) item.type = "citation";
    else if (modal.has(normalized)) item.type = "legal-modal";
    else if (/^\d/.test(item.word)) item.type = "number";
  }
}

function render() {
  renderNavigation();
  renderPanes();
  restoreComposerBody();
  renderDraft();
  renderComments();
  renderToggles();
}

function renderNavigation() {
  const select = document.querySelector("#rule-select");
  select.innerHTML = data.rules.map((rule, index) =>
    `<option value="${index}" ${index === ruleIndex ? "selected" : ""}>${index + 1}. ${rule.citations.join(" · ")} — ${rule.name}</option>`
  ).join("");
  const rule = currentRule();
  const versions = versionsForRule();
  const versionSelect = document.querySelector("#version-select");
  versionSelect.innerHTML = [...versions].reverse().map(version =>
    `<option value="${version.versionId}" ${version.versionId === rule.versionId ? "selected" : ""}>${version.versionId}${version.versionId === currentRuleFamily().currentVersion ? " · current" : " · prior"} · ${new Date(version.createdAt || 0).toLocaleString()}</option>`
  ).join("");
  document.querySelector("#rule-meta").textContent = `${rule.file}${rule.interpretiveGaps.length ? ` · ${rule.interpretiveGaps.length} interpretive gap${rule.interpretiveGaps.length === 1 ? "" : "s"}` : ""}`;
}

function renderPanes() {
  returnComposerHome();
  const root = document.querySelector("#panes");
  root.innerHTML = "";
  root.classList.toggle("wrap-text", state.preferences.wrap);
  setColumnTracks(root);
  state.preferences.paneColumns.forEach((panes, columnIndex) => {
    if (columnIndex > 0) root.append(createColumnSplitter(columnIndex - 1));
    const column = document.createElement("section");
    column.className = "pane-column";
    column.dataset.column = columnIndex;
    const visiblePanes = panes.filter(pane => state.preferences.visiblePanes.includes(pane));
    setRowTracks(column, visiblePanes);
    if (!visiblePanes.length) column.append(renderEmptyColumn(columnIndex));
    visiblePanes.forEach((pane, rowIndex) => {
      if (rowIndex > 0) column.append(createRowSplitter(columnIndex, visiblePanes[rowIndex - 1], pane, column));
      column.append(renderPane(pane));
    });
    root.append(column);
  });
}

function setColumnTracks(root) {
  root.style.gridTemplateColumns = state.preferences.columnWeights.flatMap((weight, index) => [
    ...(index ? ["10px"] : []), `minmax(0, ${weight}fr)`,
  ]).join(" ");
}

function setRowTracks(column, panes) {
  column.style.gridTemplateRows = panes.flatMap((pane, index) => [
    ...(index ? ["10px"] : []), `minmax(120px, ${state.preferences.paneHeights[pane]}fr)`,
  ]).join(" ");
}

function renderEmptyColumn(columnIndex) {
  const cell = document.createElement("div");
  cell.className = "empty-grid-cell";
  cell.innerHTML = "<span>Drop a window in this column</span>";
  cell.ondragover = event => { event.preventDefault(); cell.classList.add("drag-target"); };
  cell.ondragleave = () => cell.classList.remove("drag-target");
  cell.ondrop = event => {
    event.preventDefault(); cell.classList.remove("drag-target");
    movePaneToColumn(event.dataTransfer.getData("text/plain"), columnIndex, 0);
  };
  return cell;
}

function renderPane(column) {
    const article = document.createElement("article");
    article.className = "pane";
    article.dataset.pane = column;
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = paneData(column).label;
    header.draggable = true;
    header.title = "Drag to move this window";
    header.ondragstart = event => { event.dataTransfer.setData("text/plain", column); article.classList.add("dragging"); };
    header.ondragend = () => article.classList.remove("dragging");
    article.ondragover = event => {
      event.preventDefault();
      article.classList.add("drag-target");
      article.dataset.dropZone = dropZone(article, event);
    };
    article.ondragleave = event => {
      if (!article.contains(event.relatedTarget)) {
        article.classList.remove("drag-target");
        delete article.dataset.dropZone;
      }
    };
    article.ondrop = event => {
      event.preventDefault();
      const zone = article.dataset.dropZone || dropZone(article, event);
      article.classList.remove("drag-target");
      delete article.dataset.dropZone;
      movePane(event.dataTransfer.getData("text/plain"), column, zone);
    };
    header.append(heading);
    if (paneData(column).file) {
      const file = document.createElement("span");
      file.className = "pane-file";
      file.textContent = paneData(column).file;
      file.title = paneData(column).file;
      header.append(file);
    }
    article.append(header);
    article.append(renderCodeSection(column, paneData(column), null));
    return article;
}

function createColumnSplitter(columnIndex) {
  const splitter = document.createElement("div");
  splitter.className = "pane-splitter";
  splitter.setAttribute("role", "separator");
  splitter.setAttribute("aria-orientation", "vertical");
  splitter.setAttribute("aria-label", `Resize workspace columns ${columnIndex + 1} and ${columnIndex + 2}`);
  splitter.onpointerdown = event => {
    event.preventDefault();
    splitter.setPointerCapture(event.pointerId);
    splitter.classList.add("resizing");
    document.body.classList.add("resizing-panes");
    const startX = event.clientX;
    const startLeft = state.preferences.columnWeights[columnIndex];
    const startRight = state.preferences.columnWeights[columnIndex + 1];
    const pairTotal = startLeft + startRight;
    const pairPixels = splitter.previousElementSibling.getBoundingClientRect().width + splitter.nextElementSibling.getBoundingClientRect().width;
    splitter.onpointermove = moveEvent => {
      const deltaWeight = (moveEvent.clientX - startX) / pairPixels * pairTotal;
      const nextLeft = Math.max(0.35, Math.min(pairTotal - 0.35, startLeft + deltaWeight));
      state.preferences.columnWeights[columnIndex] = nextLeft;
      state.preferences.columnWeights[columnIndex + 1] = pairTotal - nextLeft;
      setColumnTracks(document.querySelector("#panes"));
    };
    splitter.onpointerup = () => {
      splitter.onpointermove = null;
      splitter.classList.remove("resizing");
      document.body.classList.remove("resizing-panes");
      saveState();
    };
  };
  return splitter;
}

function createRowSplitter(columnIndex, upperPane, lowerPane, column) {
  const splitter = document.createElement("div");
  splitter.className = "row-splitter";
  splitter.setAttribute("role", "separator");
  splitter.setAttribute("aria-orientation", "horizontal");
  splitter.setAttribute("aria-label", "Resize window rows");
  splitter.onpointerdown = event => {
    event.preventDefault();
    splitter.setPointerCapture(event.pointerId);
    splitter.classList.add("resizing");
    document.body.classList.add("resizing-rows");
    const startY = event.clientY;
    const startUpper = state.preferences.paneHeights[upperPane] || 1;
    const startLower = state.preferences.paneHeights[lowerPane] || 1;
    const pairTotal = startUpper + startLower;
    const pairPixels = splitter.previousElementSibling.getBoundingClientRect().height + splitter.nextElementSibling.getBoundingClientRect().height;
    splitter.onpointermove = moveEvent => {
      const deltaWeight = (moveEvent.clientY - startY) / pairPixels * pairTotal;
      const nextUpper = Math.max(0.35, Math.min(pairTotal - 0.35, startUpper + deltaWeight));
      state.preferences.paneHeights[upperPane] = nextUpper;
      state.preferences.paneHeights[lowerPane] = pairTotal - nextUpper;
      const visiblePanes = state.preferences.paneColumns[columnIndex].filter(pane => state.preferences.visiblePanes.includes(pane));
      setRowTracks(column, visiblePanes);
    };
    splitter.onpointerup = () => {
      splitter.onpointermove = null;
      splitter.classList.remove("resizing");
      document.body.classList.remove("resizing-rows");
      saveState();
    };
  };
  return splitter;
}

function renderCodeSection(pane, content, sectionLabel) {
  const section = document.createElement("section");
  section.className = "code-section";
  if (sectionLabel) {
    const label = document.createElement("div");
    label.className = "code-section-label";
    label.innerHTML = `<strong>${sectionLabel}</strong><span>${content.text.split("\n").length} lines</span>`;
    section.append(label);
  }
  const code = document.createElement("div");
  code.className = "code";
  code.dataset.pane = pane;
  let globalToken = 0;
  content.text.split("\n").forEach((text, lineIndex) => {
    const line = document.createElement("div");
    line.className = "line";
    line.dataset.line = lineIndex;
    line.dataset.pane = pane;
    const gutter = document.createElement("button");
    gutter.className = "gutter";
    gutter.textContent = String(lineIndex + 1);
    gutter.title = "Add an inline comment on this line; Shift-click to extend";
    gutter.onclick = event => selectLines(pane, lineIndex, event.shiftKey);
    const lineText = document.createElement("span");
    lineText.className = "line-text";
    let previousToken = -1;
    for (const item of tokenizeLine(text, content.language)) {
      if (item.space !== undefined) {
        const space = document.createElement("span");
        space.className = "space";
        space.textContent = item.space;
        space.dataset.pane = pane;
        space.dataset.left = previousToken;
        space.dataset.right = globalToken;
        lineText.append(space);
        continue;
      }
      const wordToken = globalToken;
      const word = document.createElement("span");
      word.className = "word";
      if (item.type) word.classList.add(`syntax-${item.type}`);
      word.textContent = item.word;
      word.dataset.pane = pane;
      word.dataset.line = lineIndex;
      word.dataset.token = wordToken;
      word.onpointerdown = event => beginWordSelection(event, pane, wordToken);
      word.onpointerenter = event => extendWordSelection(event, pane, wordToken);
      word.ondblclick = event => selectSingleWord(event, pane, wordToken);
      lineText.append(word);
      previousToken = globalToken;
      globalToken += 1;
    }
    line.append(gutter, lineText);
    code.append(line);
  });
  section.append(code);
  return section;
}

function beginWordSelection(event, pane, token) {
  if (event.button !== 0) return;
  drag = { pane, start: token, end: token, startX: event.clientX, startY: event.clientY, moved: false };
  previewAnchor = null;
}

function extendWordSelection(event, pane, token) {
  if (!drag || drag.pane !== pane || event.buttons !== 1) return;
  drag.end = token;
  drag.moved = drag.moved || token !== drag.start;
  previewAnchor = wordAnchor(pane, drag.start, drag.end);
  applyHighlights();
}

function trackWordDrag(event) {
  if (!drag || event.buttons !== 1) return;
  if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) >= 4) {
    drag.moved = true;
    previewAnchor ||= wordAnchor(drag.pane, drag.start, drag.end);
    applyHighlights();
  }
}

function finishWordSelection() {
  if (!drag) return;
  if (!drag.moved || !previewAnchor) {
    drag = null;
    previewAnchor = null;
    applyHighlights();
    return;
  }
  addDraftAnchor(previewAnchor);
  drag = null;
  previewAnchor = null;
  renderDraft();
  applyHighlights();
  document.querySelector("#comment-body")?.focus();
}

function selectSingleWord(event, pane, token) {
  event.preventDefault();
  event.stopPropagation();
  drag = null;
  previewAnchor = null;
  addDraftAnchor(wordAnchor(pane, token, token));
  renderDraft();
  applyHighlights();
  document.querySelector("#comment-body")?.focus();
}

function wordAnchor(pane, first, last) {
  const startToken = Math.min(first, last);
  const endToken = Math.max(first, last);
  const words = [];
  for (let token = startToken; token <= endToken; token += 1) {
    const word = document.querySelector(`.word[data-pane="${pane}"][data-token="${token}"]`);
    if (word) words.push(word);
  }
  return {
    kind: "words", pane, startToken, endToken,
    startLine: Number(words[0]?.dataset.line || 0),
    endLine: Number(words.at(-1)?.dataset.line || 0),
    quote: words.map(word => word.textContent).join(" "),
  };
}

function selectLines(pane, line, extend) {
  let start = line;
  if (extend && lineStarts[pane] !== undefined) start = lineStarts[pane];
  else lineStarts[pane] = line;
  const startLine = Math.min(start, line);
  const endLine = Math.max(start, line);
  const words = [...document.querySelectorAll(`.word[data-pane="${pane}"]`)]
    .filter(word => Number(word.dataset.line) >= startLine && Number(word.dataset.line) <= endLine);
  const anchor = {
    kind: "lines", pane, startLine, endLine,
    startToken: words.length ? Number(words[0].dataset.token) : -1,
    endToken: words.length ? Number(words.at(-1).dataset.token) : -1,
    quote: Array.from({ length: endLine - startLine + 1 }, (_, offset) =>
      document.querySelector(`.line[data-pane="${pane}"][data-line="${startLine + offset}"] .line-text`)?.textContent || ""
    ).join("\n"),
  };
  if (extend) {
    const draft = currentDraft();
    draft.anchors = draft.anchors.filter(item => !(item.kind === "lines" && item.pane === pane && item.startLine === start));
    updateDraft(draft);
  }
  addDraftAnchor(anchor);
  renderDraft();
  applyHighlights();
  document.querySelector("#comment-body")?.focus();
}

function addDraftAnchor(anchor) {
  const draft = currentDraft();
  const duplicate = draft.anchors.some(item => item.kind === anchor.kind && item.pane === anchor.pane && item.startToken === anchor.startToken && item.endToken === anchor.endToken && item.startLine === anchor.startLine && item.endLine === anchor.endLine);
  if (!duplicate) draft.anchors.push(anchor);
  updateDraft(draft);
}

function restoreComposerBody() {
  document.querySelector("#comment-body").value = currentDraft().body || "";
}

function renderDraft() {
  const draft = currentDraft();
  const list = document.querySelector("#draft-anchors");
  list.innerHTML = "";
  list.classList.toggle("empty", !draft.anchors.length);
  if (!draft.anchors.length) {
    list.textContent = "Drag across words or click a line number.";
    returnComposerHome();
  } else {
    draft.anchors.forEach((anchor, index) => {
      const chip = document.createElement("div");
      chip.className = "anchor-chip";
      const text = document.createElement("span");
      text.textContent = `${labelForPane(anchor.pane)} L${anchor.startLine + 1}${anchor.endLine === anchor.startLine ? "" : `–${anchor.endLine + 1}`}: “${displayQuote(anchor)}”`;
      const remove = document.createElement("button");
      remove.textContent = "×";
      remove.onclick = () => {
        const next = currentDraft();
        next.anchors.splice(index, 1);
        updateDraft(next);
        renderDraft();
        applyHighlights();
      };
      chip.append(text, remove);
      list.append(chip);
    });
    const visibleAnchor = [...draft.anchors].reverse().find(anchor => isPaneVisible(anchor.pane));
    if (visibleAnchor) mountComposer(visibleAnchor);
  }
  updateSubmit();
}

function displayQuote(anchor) {
  if (typeof anchor.quote === "string" && anchor.quote.trim()) return anchor.quote;
  const source = paneData(anchor.pane)?.text || "";
  const lines = source.split("\n").slice(anchor.startLine, anchor.endLine + 1).join("\n").trim();
  return lines || `Selected ${anchor.startLine === anchor.endLine ? "line" : "lines"}`;
}

function returnComposerHome() {
  const composer = document.querySelector(".composer");
  const home = document.querySelector("#composer-home");
  if (composer && home && composer.parentElement !== home) home.append(composer);
  document.querySelector(".draft-comment-popover")?.remove();
  syncCommentRail();
}

function mountComposer(anchor) {
  if (!isPaneVisible(anchor.pane)) return;
  returnComposerHome();
  const slot = document.createElement("div");
  slot.className = "comment-popover draft-comment-popover";
  slot.dataset.anchorPane = anchor.pane;
  slot.dataset.anchorLine = anchor.endLine;
  document.querySelector("#comment-layer").append(slot);
  const composer = document.querySelector(".composer");
  if (!composer) return;
  slot.append(composer);
  syncCommentRail();
}

function syncCommentRail() {
  const layer = document.querySelector("#comment-layer");
  const open = Boolean(layer?.children.length);
  layer?.classList.toggle("open", open);
  if (open && state.preferences.sidebarCollapsed) {
    state.preferences.sidebarCollapsed = false;
    saveState();
    applySidebarState();
  }
}

function updateSubmit() {
  const draft = currentDraft();
  document.querySelector("#submit-comment").disabled = !draft.anchors.length || !draft.body.trim();
}

function clearDraft() {
  state.drafts[reviewKey()] = { anchors: [], body: "" };
  saveState();
  document.querySelector("#comment-body").value = "";
  renderDraft();
  applyHighlights();
}

function submitComment() {
  const draft = currentDraft();
  if (!draft.body.trim() || !draft.anchors.length) return;
  state.comments.push({
    id: crypto.randomUUID(), ruleId: currentRule().id, body: draft.body.trim(),
    versionId: currentRule().versionId || "v1", anchors: structuredClone(draft.anchors),
    createdAt: new Date().toISOString(), resolved: false, replies: [],
  });
  state.drafts[reviewKey()] = { anchors: [], body: "" };
  openCommentId = state.comments.at(-1).id;
  saveState();
  document.querySelector("#comment-body").value = "";
  renderDraft();
  renderComments();
}

function commentsForRule() {
  const versionId = currentRule().versionId || "v1";
  return state.comments.filter(comment => comment.ruleId === currentRule().id && (comment.versionId || baselineVersionForRule(comment.ruleId)) === versionId);
}
function renderComments() {
  const comments = commentsForRule();
  document.querySelectorAll(".comment-marker").forEach(marker => marker.remove());
  document.querySelector(".submitted-comment-popover")?.remove();
  for (const comment of comments) {
    if (!Array.isArray(comment.anchors) || !comment.anchors.length) continue;
    for (const anchor of comment.anchors.filter(item => isPaneVisible(item.pane))) addCommentMarker(comment, anchor);
  }
  if (openCommentId) openComment(openCommentId);
  syncCommentRail();
  applyHighlights();
}

function addCommentMarker(comment, anchor) {
  const line = document.querySelector(`.line[data-pane="${anchor.pane}"][data-line="${anchor.endLine}"]`);
  if (!line) return;
  const marker = document.createElement("button");
  marker.className = `comment-marker${comment.resolved ? " resolved" : ""}`;
  marker.textContent = "●";
  marker.title = `Open comment: ${comment.body}`;
  marker.onclick = event => { event.stopPropagation(); openCommentId = comment.id; openComment(comment.id, anchor); };
  line.append(marker);
}

function openComment(commentId, preferredAnchor = null) {
  document.querySelector(".submitted-comment-popover")?.remove();
  const comment = commentsForRule().find(item => item.id === commentId);
  if (!comment) { openCommentId = null; return; }
  const anchor = preferredAnchor || comment.anchors.find(item => isPaneVisible(item.pane));
  if (!anchor) return;
  const line = document.querySelector(`.line[data-pane="${anchor.pane}"][data-line="${anchor.endLine}"]`);
  if (!line) return;
  const popover = document.createElement("div");
  popover.className = "comment-popover submitted-comment-popover";
  popover.dataset.anchorPane = anchor.pane;
  popover.dataset.anchorLine = anchor.endLine;
  const card = document.createElement("article");
  card.className = `comment-card${comment.resolved ? " resolved" : ""}`;
  card.onmouseenter = () => { activeComment = comment.id; applyHighlights(); };
  card.onmouseleave = () => { activeComment = null; applyHighlights(); };
  const meta = document.createElement("div"); meta.className = "comment-meta";
  const close = document.createElement("button"); close.className = "popover-close"; close.textContent = "×";
  close.onclick = () => { openCommentId = null; popover.remove(); syncCommentRail(); };
  meta.innerHTML = `<span>${comment.versionId || baselineVersionForRule(comment.ruleId)} · ${new Date(comment.createdAt).toLocaleString()} · ${comment.resolved ? "Resolved" : "Open"}</span>`;
  meta.append(close);
  const body = document.createElement("p"); body.textContent = comment.body;
  const thread = document.createElement("div");
  thread.className = "comment-thread";
  for (const reply of repliesFor(comment)) {
    const item = document.createElement("article");
    item.className = `comment-reply reply-${(reply.author || "reviewer").toLowerCase()}`;
    const replyMeta = document.createElement("div");
    replyMeta.className = "reply-meta";
    replyMeta.textContent = `${reply.author || "Reviewer"} · ${new Date(reply.createdAt).toLocaleString()}`;
    const replyBody = document.createElement("p");
    replyBody.textContent = reply.body;
    item.append(replyMeta, replyBody);
    thread.append(item);
  }
  const replyComposer = document.createElement("div");
  replyComposer.className = "reply-composer";
  const replyBody = document.createElement("textarea");
  replyBody.rows = 3;
  replyBody.placeholder = "Reply to this comment";
  const replyButton = document.createElement("button");
  replyButton.textContent = "Reply";
  replyButton.disabled = true;
  replyBody.oninput = () => { replyButton.disabled = !replyBody.value.trim(); };
  replyButton.onclick = () => addReply(comment, replyBody.value);
  replyComposer.append(replyBody, replyButton);
  const anchors = document.createElement("div"); anchors.className = "comment-anchors";
  for (const item of comment.anchors) {
    const button = document.createElement("button");
    button.textContent = `${labelForPane(item.pane)} L${item.startLine + 1}${item.endLine === item.startLine ? "" : `–${item.endLine + 1}`}`;
    button.onclick = () => { focusAnchor(item); requestAnimationFrame(() => openComment(comment.id, item)); };
    anchors.append(button);
  }
  const actions = document.createElement("div"); actions.className = "comment-actions";
  const resolve = document.createElement("button"); resolve.textContent = comment.resolved ? "Reopen" : "Resolve";
  resolve.onclick = () => { comment.resolved = !comment.resolved; saveState(); renderComments(); };
  const remove = document.createElement("button"); remove.textContent = "Delete";
  remove.onclick = () => { if (confirm("Delete this comment?")) { state.comments = state.comments.filter(item => item.id !== comment.id); openCommentId = null; saveState(); renderComments(); } };
  actions.append(resolve, remove); card.append(meta, body, anchors, thread, replyComposer, actions); popover.append(card);
  document.querySelector("#comment-layer").append(popover);
  syncCommentRail();
}

function repliesFor(comment) {
  const combined = [...(data.replies?.[comment.id] || []), ...(comment.replies || [])];
  const seen = new Set();
  return combined.filter(reply => {
    const key = reply.id || `${reply.author}:${reply.createdAt}:${reply.body}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function addReply(comment, body) {
  const text = body.trim();
  if (!text) return;
  comment.replies ||= [];
  comment.replies.push({
    id: crypto.randomUUID(), author: "John", body: text,
    createdAt: new Date().toISOString(),
  });
  saveState();
  openComment(comment.id);
}

function applyHighlights() {
  document.querySelectorAll(".word,.space").forEach(node => node.classList.remove("annotated", "active-annotation", "draft-anchor", "selection-preview"));
  document.querySelectorAll(".line").forEach(line => line.classList.remove("line-selected"));
  for (const comment of commentsForRule()) for (const anchor of comment.anchors) markAnchor(anchor, comment.id === activeComment ? "active-annotation" : "annotated", false);
  for (const anchor of currentDraft().anchors) markAnchor(anchor, "draft-anchor", true);
  if (previewAnchor) markAnchor(previewAnchor, "selection-preview", true);
}

function markAnchor(anchor, className, lineSelected) {
  if (anchor.kind === "lines") {
    for (let line = anchor.startLine; line <= anchor.endLine; line += 1) {
      const row = document.querySelector(`.line[data-pane="${anchor.pane}"][data-line="${line}"]`);
      if (lineSelected) row?.classList.add("line-selected");
      row?.querySelectorAll(".word,.space").forEach(node => node.classList.add(className));
    }
    return;
  }
  for (let token = anchor.startToken; token <= anchor.endToken; token += 1) {
    document.querySelector(`.word[data-pane="${anchor.pane}"][data-token="${token}"]`)?.classList.add(className);
  }
  document.querySelectorAll(`.space[data-pane="${anchor.pane}"]`).forEach(space => {
    const left = Number(space.dataset.left), right = Number(space.dataset.right);
    if (left >= anchor.startToken && right <= anchor.endToken) space.classList.add(className);
  });
}

function labelForPane(pane) { return paneData(pane).label; }
function isPaneVisible(pane) { return state.preferences.visiblePanes.includes(pane); }
function focusAnchor(anchor) {
  if (!state.preferences.visiblePanes.includes(anchor.pane)) state.preferences.visiblePanes.push(anchor.pane);
  saveState(); render();
  requestAnimationFrame(() => document.querySelector(`.line[data-pane="${anchor.pane}"][data-line="${anchor.startLine}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
}

function togglePane(pane) {
  const visible = state.preferences.visiblePanes;
  if (visible.includes(pane)) {
    if (visible.length === 1) return;
    state.preferences.visiblePanes = visible.filter(item => item !== pane);
  } else state.preferences.visiblePanes.push(pane);
  saveState(); renderPanes(); renderDraft(); renderComments(); renderToggles();
}

function dropZone(article, event) {
  const bounds = article.getBoundingClientRect();
  const x = (event.clientX - bounds.left) / bounds.width - 0.5;
  const y = (event.clientY - bounds.top) / bounds.height - 0.5;
  if (Math.abs(x) > Math.abs(y)) return x < 0 ? "left" : "right";
  return y < 0 ? "top" : "bottom";
}

function movePane(source, target, zone) {
  if (!columnOrder.includes(source) || source === target) return;
  detachPane(source);
  const targetColumn = state.preferences.paneColumns.findIndex(column => column.includes(target));
  if (targetColumn < 0) return;
  if (zone === "top" || zone === "bottom") {
    const targetRow = state.preferences.paneColumns[targetColumn].indexOf(target);
    state.preferences.paneColumns[targetColumn].splice(targetRow + (zone === "bottom" ? 1 : 0), 0, source);
  } else {
    const insertion = targetColumn + (zone === "right" ? 1 : 0);
    state.preferences.paneColumns.splice(insertion, 0, [source]);
    state.preferences.columnWeights.splice(insertion, 0, 1);
  }
  saveState(); renderPanes(); renderDraft(); renderComments();
}

function detachPane(pane) {
  const columnIndex = state.preferences.paneColumns.findIndex(column => column.includes(pane));
  if (columnIndex < 0) return;
  state.preferences.paneColumns[columnIndex] = state.preferences.paneColumns[columnIndex].filter(item => item !== pane);
  if (!state.preferences.paneColumns[columnIndex].length) {
    state.preferences.paneColumns.splice(columnIndex, 1);
    state.preferences.columnWeights.splice(columnIndex, 1);
  }
}

function movePaneToColumn(pane, columnIndex, rowIndex) {
  if (!columnOrder.includes(pane)) return;
  detachPane(pane);
  const targetColumn = Math.min(columnIndex, state.preferences.paneColumns.length - 1);
  state.preferences.paneColumns[targetColumn].splice(rowIndex, 0, pane);
  saveState(); renderPanes(); renderDraft(); renderComments();
}

function resetLayout() {
  state.preferences = structuredClone(defaultPreferences);
  saveState(); render();
}

function renderToggles() {
  document.querySelectorAll("[data-toggle-pane]").forEach(button => {
    const active = state.preferences.visiblePanes.includes(button.dataset.togglePane);
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
  const wrap = document.querySelector("#toggle-wrap"); wrap.classList.toggle("active", state.preferences.wrap); wrap.setAttribute("aria-pressed", String(state.preferences.wrap)); wrap.textContent = state.preferences.wrap ? "Unwrap text" : "Wrap text";
  applySidebarState();
}

function applySidebarState() {
  const collapsed = Boolean(state.preferences.sidebarCollapsed);
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  document.body.classList.toggle("sidebar-mobile-open", !collapsed);
  const toggle = document.querySelector("#toggle-sidebar");
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
}

function toggleSidebar() {
  state.preferences.sidebarCollapsed = !state.preferences.sidebarCollapsed;
  saveState();
  applySidebarState();
}

function changeRule(next) { ruleIndex = (next + data.rules.length) % data.rules.length; activeComment = null; openCommentId = null; drag = null; previewAnchor = null; render(); }
function changeVersion(versionId) {
  versionSelections[currentRuleFamily().id] = versionId;
  activeComment = null; openCommentId = null; drag = null; previewAnchor = null;
  render();
}
function exportReview() {
  const payload = { schemaVersion: 2, corpusSchemaVersion: data.schemaVersion, exportedAt: new Date().toISOString(), comments: state.comments, drafts: state.drafts, preferences: state.preferences };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "zoning-language-review.json"; link.click(); URL.revokeObjectURL(link.href);
}
async function importReview(file) { const payload = JSON.parse(await file.text()); if (!Array.isArray(payload.comments)) throw new Error("Review file has no comments array"); state.comments = payload.comments; state.drafts = payload.drafts || {}; if (payload.preferences) state.preferences = payload.preferences; saveState(); state = loadState(); render(); }

document.querySelector("#rule-select").onchange = event => changeRule(Number(event.target.value));
document.querySelector("#version-select").onchange = event => changeVersion(event.target.value);
document.querySelector("#previous-rule").onclick = () => changeRule(ruleIndex - 1);
document.querySelector("#next-rule").onclick = () => changeRule(ruleIndex + 1);
document.querySelectorAll("[data-toggle-pane]").forEach(button => button.onclick = () => togglePane(button.dataset.togglePane));
document.querySelector("#toggle-wrap").onclick = () => { state.preferences.wrap = !state.preferences.wrap; saveState(); document.querySelector("#panes").classList.toggle("wrap-text", state.preferences.wrap); renderToggles(); };
document.querySelector("#reset-layout").onclick = resetLayout;
document.querySelector("#toggle-sidebar").onclick = toggleSidebar;
document.querySelector("#clear-draft").onclick = clearDraft;
document.querySelector("#comment-body").oninput = event => { const draft = currentDraft(); draft.body = event.target.value; updateDraft(draft); updateSubmit(); };
document.querySelector("#submit-comment").onclick = submitComment;
document.querySelector("#export-review").onclick = exportReview;
document.querySelector("#import-review").onchange = async event => { try { await importReview(event.target.files[0]); } catch (error) { alert(error.message); } };
document.addEventListener("pointermove", trackWordDrag);
document.addEventListener("pointerup", finishWordSelection);
render();
