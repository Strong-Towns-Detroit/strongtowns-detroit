/**
 * Strong Towns Detroit data-graphics configuration.
 *
 * Public API:
 *   STDetroitGraphics.configure({ typography: "open-editorial" })
 *   STDetroitGraphics.getConfig()
 *   STDetroitGraphics.presets
 *
 * Precedence on initial load:
 *   ?typography=... URL parameter → saved local preference → brand-safe default.
 */
(function initializeGraphicsConfig(global) {
  "use strict";

  const presets = Object.freeze({
    "brand-safe": Object.freeze({
      label: "Brand-guide fallback",
      display: 'Georgia, "Times New Roman", serif',
      body: 'Georgia, "Times New Roman", serif',
      data: "Arial, Helvetica, sans-serif",
      ui: "Arial, Helvetica, sans-serif",
      source: "Strong Towns quick-reference guide"
    }),
    "open-editorial": Object.freeze({
      label: "Open-source editorial",
      display: '"Fraunces", Georgia, serif',
      body: '"Source Serif 4", Georgia, serif',
      data: '"Source Sans 3", Arial, sans-serif',
      ui: '"Source Sans 3", Arial, sans-serif',
      source: "SIL Open Font License families"
    })
  });

  const storageKey = "st-detroit-graphics-typography";
  const fallback = "brand-safe";

  function validPreset(value) {
    return Object.prototype.hasOwnProperty.call(presets, value);
  }

  function configure(options = {}) {
    const requested = options.typography || fallback;
    if (!validPreset(requested)) {
      throw new RangeError(
        `Unknown typography preset "${requested}". Expected one of: ${Object.keys(presets).join(", ")}`
      );
    }
    document.body.dataset.typePreset = requested;
    if (options.persist !== false) {
      try { global.localStorage.setItem(storageKey, requested); } catch (_) { /* storage optional */ }
    }
    document.dispatchEvent(new CustomEvent("stgraphics:configchange", {
      detail: { typography: requested, preset: presets[requested] }
    }));
    return getConfig();
  }

  function getConfig() {
    const typography = document.body.dataset.typePreset || fallback;
    return Object.freeze({ typography, preset: presets[typography] });
  }

  function initialPreset() {
    const query = new URLSearchParams(global.location.search).get("typography");
    if (validPreset(query)) return query;
    try {
      const saved = global.localStorage.getItem(storageKey);
      if (validPreset(saved)) return saved;
    } catch (_) { /* storage optional */ }
    return fallback;
  }

  global.STDetroitGraphics = Object.freeze({ configure, getConfig, presets });
  configure({ typography: initialPreset(), persist: false });

  document.addEventListener("DOMContentLoaded", () => {
    const select = document.querySelector("#type-preset");
    if (!select) return;
    select.value = getConfig().typography;
    select.addEventListener("change", () => {
      configure({ typography: select.value });
      const url = new URL(global.location.href);
      url.searchParams.set("typography", select.value);
      global.history.replaceState({}, "", url);
    });
  });
})(window);
