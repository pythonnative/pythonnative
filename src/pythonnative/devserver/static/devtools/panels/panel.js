// The base of every DevTools panel. The app calls these hooks:
//
// - onShow() / onHide(): the tab became visible or hidden.
// - onTarget(target, previousId): the selected app changed.
// - onTargets(targets): the list of apps changed.
// - onEvent(event, replay): an app event; `replay` during history.
// - onHistoryStart() / onHistoryEnd(): the server is replaying history
//   (after every connect), so stores reset first.
// - onConnection(state), onConnectDoc(doc), onDebug(message).
// - badges(): `[{text, cls}]` for the tab.
// - focusSearch(): focus the panel's filter; returns whether it did.

import { h } from "../util.js";

export class Panel {
  constructor(app, id, title) {
    this.app = app;
    this.id = id;
    this.title = title;
    this.el = h("section");
    this.visible = false;
  }

  onShow() {
    this.visible = true;
  }

  onHide() {
    this.visible = false;
  }

  /** A centered empty-state message. */
  static empty(title, detail = "", ...extra) {
    return h("div.empty", null, h("div.empty-title", null, title), detail ? h("div.empty-detail", null, detail) : null, ...extra);
  }
}

/** A search box with an icon: `searchBox("Filter", onInput)`. */
export function searchBox(placeholder, onInput, value = "") {
  const input = h("input.search-input", { type: "search", placeholder, value, spellcheck: "false", "aria-label": placeholder });
  input.addEventListener("input", () => onInput(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && input.value) {
      input.value = "";
      onInput("");
      event.stopPropagation();
    }
  });
  return input;
}
