// Console: log output from every app, problems inline, reload markers,
// and a Python REPL bound to the selected app.

import { Panel, searchBox } from "./panel.js";
import { clock, h, icon, prefs } from "../util.js";

const MAX_ENTRIES = 3000;
const HISTORY_SIZE = 100;
const LEVELS = { error: "error", warning: "warning", warn: "warning", info: "info", debug: "info", ok: "info" };

export class ConsolePanel extends Panel {
  constructor(app) {
    super(app, "console", "Console");
    this.entries = [];
    this.level = prefs.get("console:level", "all");
    this.targetFilter = "all";
    this.text = "";
    this.stick = true;
    this.unseen = 0;
    this.history = prefs.get("console:history", []);
    this.historyIndex = this.history.length;
    this.draft = "";
    this.build();
  }

  build() {
    this.el.classList.add("console");
    this.levelSelect = h(
      "select.select",
      { "aria-label": "Levels", title: "Show these levels" },
      h("option", { value: "all" }, "All levels"),
      h("option", { value: "error" }, "Errors"),
      h("option", { value: "warning" }, "Warnings and errors"),
      h("option", { value: "info" }, "Info"),
    );
    this.levelSelect.value = this.level;
    this.levelSelect.addEventListener("change", () => {
      this.level = this.levelSelect.value;
      prefs.set("console:level", this.level);
      this.renderAll();
    });
    this.targetSelect = h("select.select", { "aria-label": "Apps", title: "Show output from" });
    this.targetSelect.addEventListener("change", () => {
      this.targetFilter = this.targetSelect.value;
      this.renderAll();
    });
    this.search = searchBox("Filter output", (value) => {
      this.text = value.toLowerCase();
      this.renderAll();
    });
    this.count = h("span.toolbar-note");
    const toolbar = h(
      "div.toolbar",
      null,
      h("button.btn.btn-icon", { type: "button", title: "Clear the console", onclick: () => this.clear() }, icon("clear", 14)),
      h("span.toolbar-sep"),
      this.search,
      this.levelSelect,
      this.targetSelect,
      h("span.spacer"),
      this.count,
    );

    this.list = h("div.log", { role: "log", "aria-live": "off", tabIndex: 0 });
    this.list.addEventListener("scroll", () => {
      const near = this.list.scrollHeight - this.list.scrollTop - this.list.clientHeight < 24;
      this.stick = near;
      if (near) this.setUnseen(0);
    });
    this.jump = h(
      "button.jump",
      { type: "button", hidden: true, onclick: () => this.scrollToEnd() },
      icon("down", 12),
      h("span", null, "New output"),
    );

    this.input = h("textarea.repl-input", {
      rows: 1,
      spellcheck: "false",
      autocomplete: "off",
      "aria-label": "Python to evaluate",
    });
    this.input.addEventListener("keydown", (event) => this.onInputKey(event));
    this.input.addEventListener("input", () => this.autosize());
    this.replTarget = h("span.repl-target");
    const repl = h("div.repl", null, h("span.repl-prompt", { "aria-hidden": "true" }, "›"), this.input, this.replTarget);
    repl.addEventListener("click", (event) => {
      if (event.target === repl) this.input.focus();
    });

    this.el.append(toolbar, h("div.log-wrap", null, this.list, this.jump), repl);
    this.updateTargets([]);
    this.updatePlaceholder();
  }

  focusSearch() {
    this.search.focus();
    return true;
  }

  onShow() {
    super.onShow();
    if (this.stick) this.scrollToEnd();
  }

  // -- data ---------------------------------------------------------------------

  onHistoryStart() {
    this.entries = this.entries.filter((entry) => entry.kind === "input" || entry.kind === "result" || entry.kind === "system");
    this.replaying = true;
  }

  onHistoryEnd() {
    this.replaying = false;
    this.entries.sort((a, b) => a.time - b.time);
    this.renderAll();
  }

  onEvent(event, replay) {
    const data = event.data || {};
    const base = { target: event.target, time: event.time || Date.now() / 1000 };
    let entry = null;
    if (event.topic === "log") {
      const text = String(data.text ?? "").replace(/\n+$/, "");
      entry = { ...base, kind: "log", level: LEVELS[data.level] || "info", text };
    } else if (event.topic === "problem") {
      entry = { ...base, kind: "problem", level: data.level === "warning" ? "warning" : "error", text: data.title || data.message || "Error", report: data };
    } else if (event.topic === "reload") {
      const modules = Array.isArray(data.modules) && data.modules.length ? `: ${data.modules.join(", ")}` : "";
      const mode = data.mode === "fast_refresh" ? "Fast Refresh" : data.mode === "remount" ? "Remounted" : "Reloaded";
      entry = { ...base, kind: "reload", level: "info", text: `${mode}${modules}` };
    }
    if (entry) this.add(entry, replay);
  }

  onTargets(targets) {
    this.updateTargets(targets);
    this.updatePlaceholder();
  }

  onTarget() {
    this.updatePlaceholder();
  }

  /** A DevTools-originated note (debugger attached, ...). */
  system(text) {
    this.add({ kind: "system", level: "info", text, target: null, time: Date.now() / 1000 }, false);
  }

  add(entry, replay) {
    this.entries.push(entry);
    if (this.entries.length > MAX_ENTRIES) this.entries.splice(0, this.entries.length - MAX_ENTRIES);
    if (replay || this.replaying) return;
    if (!this.matches(entry)) return;
    this.list.querySelector(".empty")?.remove();
    this.list.appendChild(this.entryElement(entry));
    while (this.list.childElementCount > MAX_ENTRIES) this.list.firstChild.remove();
    if (this.stick) this.scrollToEnd();
    else this.setUnseen(this.unseen + 1);
    this.updateCount();
  }

  clear() {
    this.entries = [];
    this.app.conn.send({ type: "clear", target: null, topic: "log" });
    this.renderAll();
  }

  matches(entry) {
    // The REPL's own lines always show; filters are for app output.
    const app = entry.kind !== "input" && entry.kind !== "result" && entry.kind !== "system";
    if (app && this.level === "error" && entry.level !== "error") return false;
    if (app && this.level === "warning" && entry.level === "info") return false;
    if (app && this.level === "info" && entry.level !== "info") return false;
    if (this.targetFilter !== "all" && entry.target && entry.target !== this.targetFilter) return false;
    if (this.text && !String(entry.text).toLowerCase().includes(this.text)) return false;
    return true;
  }

  // -- rendering ------------------------------------------------------------------

  renderAll() {
    this.list.textContent = "";
    const fragment = document.createDocumentFragment();
    let shown = 0;
    for (const entry of this.entries) {
      if (!this.matches(entry)) continue;
      fragment.appendChild(this.entryElement(entry));
      shown += 1;
    }
    if (!shown) {
      this.list.appendChild(
        this.entries.length
          ? Panel.empty("Nothing matches the filters")
          : Panel.empty("No output yet", "print() output, logging records, warnings, and errors from every app appear here."),
      );
    }
    this.list.appendChild(fragment);
    this.stick = true;
    this.setUnseen(0);
    this.scrollToEnd();
    this.updateCount();
  }

  updateCount() {
    const errors = this.entries.filter((e) => e.level === "error" && e.kind !== "result" && e.kind !== "input").length;
    const warnings = this.entries.filter((e) => e.level === "warning").length;
    const parts = [];
    if (errors) parts.push(`${errors} error${errors === 1 ? "" : "s"}`);
    if (warnings) parts.push(`${warnings} warning${warnings === 1 ? "" : "s"}`);
    this.count.textContent = parts.join(", ");
  }

  entryElement(entry) {
    const label = entry.target ? this.app.targetLabel(entry.target) : "";
    if (entry.kind === "reload") {
      return h("div.entry.entry-reload", null, h("span.entry-rule"), h("span", null, `${entry.text} · ${label} · ${clock(entry.time)}`), h("span.entry-rule"));
    }
    const levelClass = `level-${entry.level}`;
    const row = h(`div.entry.${levelClass}.entry-${entry.kind}`);
    row.appendChild(h("span.entry-time", { title: clock(entry.time, { millis: true }) }, clock(entry.time)));
    row.appendChild(h("span.entry-target", { title: label }, label));
    const glyph = entry.kind === "input" ? "›" : entry.kind === "result" ? "‹" : entry.level === "error" ? "✕" : entry.level === "warning" ? "!" : "";
    row.appendChild(h("span.entry-glyph", { "aria-hidden": "true" }, glyph));
    const body = h("span.entry-text", null, entry.text);
    if (entry.kind === "result" && entry.type && entry.level !== "error") body.title = entry.type;
    row.appendChild(body);
    if (entry.kind === "problem") {
      body.classList.add("entry-link");
      body.title = "Show in Problems";
      body.addEventListener("click", () => this.app.panels.find((p) => p.id === "problems")?.reveal(entry.report));
    }
    return row;
  }

  scrollToEnd() {
    this.list.scrollTop = this.list.scrollHeight;
    this.stick = true;
    this.setUnseen(0);
  }

  setUnseen(count) {
    this.unseen = count;
    this.jump.hidden = count === 0;
    this.jump.querySelector("span").textContent = count ? `${count} new` : "New output";
  }

  updateTargets(targets) {
    const current = this.targetFilter;
    this.targetSelect.textContent = "";
    this.targetSelect.appendChild(h("option", { value: "all" }, "All apps"));
    for (const target of targets) this.targetSelect.appendChild(h("option", { value: target.id }, target.label || target.id));
    this.targetSelect.value = targets.some((t) => t.id === current) ? current : "all";
    if (this.targetSelect.value !== current) {
      this.targetFilter = this.targetSelect.value;
      this.renderAll();
    }
  }

  // -- REPL -------------------------------------------------------------------------

  updatePlaceholder() {
    const target = this.app.target?.();
    this.input.disabled = !target;
    this.replTarget.textContent = target ? target.label : "";
    this.input.placeholder = target
      ? `Evaluate Python in ${target.label}. \`node\` is the selected component; top-level await works. Shift+Enter for a new line.`
      : "Connect an app to evaluate Python in it";
  }

  /** Put `node` in the REPL (from the Components inspector). */
  useNode() {
    this.app.selectTab(this.id);
    if (!this.input.value.trim()) this.input.value = "node";
    this.input.focus();
    this.input.setSelectionRange(this.input.value.length, this.input.value.length);
    this.autosize();
  }

  autosize() {
    this.input.style.height = "auto";
    this.input.style.height = `${Math.min(this.input.scrollHeight, 200)}px`;
  }

  onInputKey(event) {
    const input = this.input;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      this.evaluate();
      return;
    }
    const value = input.value;
    const caret = input.selectionStart;
    if (event.key === "ArrowUp" && !value.slice(0, caret).includes("\n") && input.selectionEnd === caret) {
      if (this.historyIndex === 0) return;
      if (this.historyIndex === this.history.length) this.draft = value;
      this.historyIndex -= 1;
      this.setInput(this.history[this.historyIndex]);
      event.preventDefault();
    } else if (event.key === "ArrowDown" && !value.slice(caret).includes("\n") && input.selectionEnd === caret) {
      if (this.historyIndex >= this.history.length) return;
      this.historyIndex += 1;
      this.setInput(this.historyIndex === this.history.length ? this.draft : this.history[this.historyIndex]);
      event.preventDefault();
    } else if (event.key === "l" && event.ctrlKey) {
      event.preventDefault();
      this.clear();
    }
  }

  setInput(value) {
    this.input.value = value;
    this.autosize();
    this.input.setSelectionRange(value.length, value.length);
  }

  async evaluate() {
    const code = this.input.value;
    if (!code.trim()) return;
    const target = this.app.targetId;
    if (!target) return;
    if (this.history[this.history.length - 1] !== code) {
      this.history.push(code);
      if (this.history.length > HISTORY_SIZE) this.history.splice(0, this.history.length - HISTORY_SIZE);
      prefs.set("console:history", this.history);
    }
    this.historyIndex = this.history.length;
    this.draft = "";
    this.setInput("");
    this.stick = true;
    this.add({ kind: "input", level: "info", text: code, target, time: Date.now() / 1000 }, false);
    try {
      const result = await this.app.conn.rpc(target, "eval", { code }, { timeout: 60000 });
      if (result?.ok === false) {
        this.add({ kind: "result", level: "error", text: String(result.error || "error"), target, time: Date.now() / 1000 }, false);
      } else if (result?.repr != null) {
        this.add({ kind: "result", level: "info", text: String(result.repr), type: result.type, target, time: Date.now() / 1000 }, false);
      }
    } catch (err) {
      this.add({ kind: "result", level: "error", text: err.message, target, time: Date.now() / 1000 }, false);
    }
  }
}
