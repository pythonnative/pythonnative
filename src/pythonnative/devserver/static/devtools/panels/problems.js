// Problems: errors and warnings from every app, with component stacks,
// source excerpts, collapsed framework frames, and editor links.

import { Panel, searchBox } from "./panel.js";
import { clock, copyButton, h, icon } from "../util.js";
import { phaseLabel, renderReport } from "../report.js";

const MAX_PROBLEMS = 300;

/** Identity for collapsing repeats: same app, level, and traceback. */
export function problemKey(target, report) {
  return `${target}|${report?.level}|${report?.text || report?.title || report?.message || ""}`;
}

export class ProblemsPanel extends Panel {
  constructor(app) {
    super(app, "problems", "Problems");
    this.items = []; // newest last: {key, target, report, time, count, open}
    this.filter = "all";
    this.text = "";
    this.build();
  }

  build() {
    this.el.classList.add("problems");
    this.filterSelect = h(
      "select.select",
      { "aria-label": "Show" },
      h("option", { value: "all" }, "Errors and warnings"),
      h("option", { value: "error" }, "Errors"),
      h("option", { value: "warning" }, "Warnings"),
    );
    this.filterSelect.addEventListener("change", () => {
      this.filter = this.filterSelect.value;
      this.render();
    });
    this.search = searchBox("Filter problems", (value) => {
      this.text = value.toLowerCase();
      this.render();
    });
    this.summary = h("span.toolbar-note");
    this.list = h("div.problem-list", { role: "list" });
    this.el.append(
      h(
        "div.toolbar",
        null,
        h("button.btn.btn-icon", { type: "button", title: "Clear problems", onclick: () => this.clear() }, icon("clear", 14)),
        h("span.toolbar-sep"),
        this.search,
        this.filterSelect,
        h("span.spacer"),
        this.summary,
      ),
      this.list,
    );
    this.render();
  }

  focusSearch() {
    this.search.focus();
    return true;
  }

  onHistoryStart() {
    this.items = [];
    this.replaying = true;
  }

  onHistoryEnd() {
    this.replaying = false;
    this.render();
    this.app.updateBadges(this);
  }

  onEvent(event, replay) {
    if (event.topic !== "problem" || !event.data) return;
    const report = event.data;
    const key = problemKey(event.target, report);
    const last = this.items[this.items.length - 1];
    if (last && last.key === key) {
      last.count += 1;
      last.time = event.time || last.time;
    } else {
      this.items.push({ key, target: event.target, report, time: event.time || Date.now() / 1000, count: 1, open: false });
      if (this.items.length > MAX_PROBLEMS) this.items.splice(0, this.items.length - MAX_PROBLEMS);
    }
    if (replay || this.replaying) return;
    this.render();
    this.app.updateBadges(this);
  }

  badges() {
    const errors = this.items.filter((item) => item.report.level !== "warning").length;
    const warnings = this.items.length - errors;
    const out = [];
    if (errors) out.push({ text: errors, cls: "badge-error" });
    if (warnings) out.push({ text: warnings, cls: "badge-warning" });
    return out;
  }

  clear() {
    this.items = [];
    this.app.conn.send({ type: "clear", target: null, topic: "problem" });
    this.render();
    this.app.updateBadges(this);
  }

  /** Show and expand the problem for `report` (from the Console). */
  reveal(report) {
    this.app.selectTab(this.id);
    const item = [...this.items].reverse().find((entry) => entry.report === report || entry.report.text === report?.text);
    if (!item) return;
    item.open = true;
    this.filter = "all";
    this.filterSelect.value = "all";
    this.render();
    this.list.querySelector(`[data-key="${CSS.escape(item.key)}"]`)?.scrollIntoView({ block: "start" });
  }

  matches(item) {
    const level = item.report.level === "warning" ? "warning" : "error";
    if (this.filter !== "all" && level !== this.filter) return false;
    if (this.text) {
      const haystack = `${item.report.title || ""}\n${item.report.text || ""}`.toLowerCase();
      if (!haystack.includes(this.text)) return false;
    }
    return true;
  }

  render() {
    this.list.textContent = "";
    const shown = [...this.items].reverse().filter((item) => this.matches(item));
    if (!shown.length) {
      this.list.appendChild(
        this.items.length
          ? Panel.empty("Nothing matches the filters")
          : Panel.empty("No problems", "Errors and warnings from every app appear here, with their component stacks and source."),
      );
    }
    for (const item of shown) this.list.appendChild(this.itemElement(item));
    const errors = this.items.filter((i) => i.report.level !== "warning").length;
    const warnings = this.items.length - errors;
    this.summary.textContent = this.items.length ? `${errors} error${errors === 1 ? "" : "s"}, ${warnings} warning${warnings === 1 ? "" : "s"}` : "";
  }

  itemElement(item) {
    const report = item.report;
    const warning = report.level === "warning";
    const head = h(
      "button.problem-head",
      { type: "button", "aria-expanded": String(item.open) },
      h("span.twisty.has-children" + (item.open ? ".open" : ""), { "aria-hidden": "true" }),
      h(`span.problem-icon.${warning ? "is-warning" : "is-error"}`, { "aria-hidden": "true" }, warning ? "!" : "✕"),
      h("span.problem-title", null, report.title || `${report.type || "Error"}: ${report.message || ""}`),
      item.count > 1 ? h("span.badge.badge-count", { title: `${item.count} times` }, `×${item.count}`) : null,
      h("span.spacer"),
      h("span.problem-meta", null, phaseLabel(report)),
      h("span.problem-meta.problem-target", null, this.app.targetLabel(item.target)),
      h("span.problem-meta", null, clock(item.time)),
    );
    const el = h(`div.problem.${warning ? "is-warning" : "is-error"}`, { role: "listitem", dataset: { key: item.key } }, head);
    head.addEventListener("click", () => {
      item.open = !item.open;
      el.replaceWith(this.itemElement(item));
    });
    if (item.open) {
      const body = h("div.problem-body");
      body.appendChild(renderReport(report, { onOpen: (file, line) => this.app.openInEditor(file, line) }));
      const actions = h("div.problem-actions", null, copyButton(() => report.text || report.title || "", "Copy traceback"));
      body.appendChild(actions);
      el.appendChild(body);
    }
    return el;
  }
}
