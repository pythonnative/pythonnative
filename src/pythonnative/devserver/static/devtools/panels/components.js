// Components: the selected app's component tree and an inspector for the
// selected node (props, hooks, context, layout, source).

import { Panel, searchBox } from "./panel.js";
import { debounce, h, icon, prefs } from "../util.js";
import { flattenTree, pathTo, revealTarget } from "../tree.js";
import { valueRow, valueText } from "../values.js";

const REFRESH_MS = 2000;
const HOOK_NAMES = {
  use_state: "State",
  use_reducer: "Reducer",
  use_ref: "Ref",
  use_memo: "Memo",
  use_callback: "Callback",
  use_effect: "Effect",
  use_layout_effect: "Layout effect",
  use_resource: "Resource",
  use_context: "Context",
  state: "State",
};
const KIND_BADGES = { provider: "Provider", boundary: "Error boundary", suspense: "Suspense", fragment: "Fragment" };

export class ComponentsPanel extends Panel {
  constructor(app) {
    super(app, "components", "Components");
    this.screens = [];
    this.treeJSON = "";
    this.loaded = false;
    this.rows = [];
    this.parents = new Map();
    this.collapsed = new Set();
    this.query = "";
    this.showFramework = !!prefs.get("showFramework", false);
    this.selectedId = null;
    this.inspected = null;
    this.inspectSeq = 0;
    this.inspecting = false;
    this.refreshing = null;
    this.timer = 0;
    this.treeError = null;
    this.hoverId = null;
    this.highlight = debounce((id) => this.sendHighlight(id), 60);
    this.inspectSoon = debounce((id) => this.inspect(id), 90);
    this.build();
  }

  // -- layout ---------------------------------------------------------------

  build() {
    this.el.classList.add("components");
    this.inspectButton = h(
      "button.btn.btn-icon.toggle",
      {
        type: "button",
        "aria-pressed": "false",
        title: "Select an element on the device to inspect it",
        onclick: () => this.toggleInspecting(),
      },
      icon("inspect", 15),
    );
    this.search = searchBox("Search components", (value) => {
      this.query = value;
      this.renderTree();
    });
    this.frameworkToggle = h("input", { type: "checkbox", checked: this.showFramework });
    this.frameworkToggle.addEventListener("change", () => {
      this.showFramework = this.frameworkToggle.checked;
      prefs.set("showFramework", this.showFramework);
      this.renderTree();
    });
    const toolbar = h(
      "div.toolbar",
      null,
      this.inspectButton,
      h("span.toolbar-sep"),
      this.search,
      h("label.check", { title: "Show PythonNative's own components and fragments" }, this.frameworkToggle, "Framework"),
      h("button.btn.btn-icon", { type: "button", title: "Refresh the tree", onclick: () => this.refresh(true) }, icon("reload", 14)),
    );
    this.tree = h("div.tree", { role: "tree", tabIndex: 0, "aria-label": "Component tree" });
    this.tree.addEventListener("click", (event) => this.onTreeClick(event));
    this.tree.addEventListener("dblclick", (event) => {
      const row = event.target.closest(".tree-row");
      if (row && !event.target.closest(".twisty")) this.toggle(Number(row.dataset.id));
    });
    this.tree.addEventListener("mousemove", (event) => {
      const row = event.target.closest(".tree-row");
      const id = row ? Number(row.dataset.id) : null;
      if (id !== this.hoverId) {
        this.hoverId = id;
        this.highlight(id);
      }
    });
    this.tree.addEventListener("mouseleave", () => {
      this.hoverId = null;
      this.highlight(null);
    });
    this.tree.addEventListener("keydown", (event) => this.onTreeKey(event));
    this.status = h("div.statusline");
    const treePane = h("div.pane.tree-pane", null, toolbar, this.tree, this.status);
    treePane.style.flexBasis = `${prefs.get("treeWidth", 420)}px`;

    const resizer = h("div.resizer", { role: "separator", "aria-orientation": "vertical", title: "Drag to resize" });
    resizer.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      resizer.setPointerCapture(event.pointerId);
      const start = event.clientX;
      const width = treePane.getBoundingClientRect().width;
      const move = (e) => {
        const next = Math.max(220, Math.min(window.innerWidth - 280, width + e.clientX - start));
        treePane.style.flexBasis = `${next}px`;
      };
      const up = () => {
        resizer.removeEventListener("pointermove", move);
        resizer.removeEventListener("pointerup", up);
        prefs.set("treeWidth", Math.round(treePane.getBoundingClientRect().width));
      };
      resizer.addEventListener("pointermove", move);
      resizer.addEventListener("pointerup", up);
    });

    this.inspector = h("div.pane.inspector-pane", { "aria-live": "polite" });
    this.el.appendChild(h("div.split", null, treePane, resizer, this.inspector));
    this.renderInspector();
    this.renderTree();
  }

  focusSearch() {
    this.search.focus();
    this.search.select();
    return true;
  }

  // -- lifecycle -----------------------------------------------------------------

  onShow() {
    super.onShow();
    this.refresh(true);
    clearInterval(this.timer);
    this.timer = setInterval(() => {
      if (!document.hidden) this.refresh(false);
    }, REFRESH_MS);
  }

  onHide() {
    super.onHide();
    clearInterval(this.timer);
    this.timer = 0;
    this.highlight(null);
  }

  onPageHide() {
    this.sendHighlight(null);
  }

  onConnection(state) {
    if (state === "open" && this.visible) this.refresh(true);
  }

  async onTarget(target) {
    this.screens = [];
    this.treeJSON = "";
    this.loaded = false;
    this.treeError = null;
    this.collapsed.clear();
    this.selectedId = null;
    this.inspected = null;
    this.setInspecting(false);
    this.renderTree();
    this.renderInspector();
    if (!target) return;
    if (this.visible) this.refresh(true);
    try {
      const status = await this.app.rpc("status");
      if (this.app.targetId === target.id) this.setInspecting(!!status?.inspecting);
    } catch (err) {
      /* an older agent; the button starts off */
    }
  }

  onEvent(event, replay) {
    if (event.target !== this.app.targetId || replay) return;
    if (event.topic === "inspecting") this.setInspecting(!!event.data?.enabled);
    else if (event.topic === "select") this.onDeviceSelect(event.data || {});
    else if (event.topic === "reload") setTimeout(() => this.refresh(true), 250);
  }

  // -- tree data -----------------------------------------------------------------

  /** Fetch the tree; re-renders only when it changed (or `force`). */
  refresh(force) {
    if (!this.app.targetId || this.app.conn.state !== "open") return Promise.resolve();
    if (this.refreshing) return this.refreshing;
    const target = this.app.targetId;
    this.refreshing = this.app
      .rpc("tree", {}, { timeout: 15000 })
      .then((result) => {
        if (target !== this.app.targetId) return;
        const screens = Array.isArray(result?.screens) ? result.screens : [];
        const json = JSON.stringify(screens);
        this.treeError = null;
        const changed = json !== this.treeJSON;
        this.loaded = true;
        if (!changed && !force) return;
        this.screens = screens;
        this.treeJSON = json;
        this.renderTree();
        if (changed && this.selectedId != null && !this.editing()) this.inspect(this.selectedId, { quiet: true });
      })
      .catch((err) => {
        if (target !== this.app.targetId) return;
        this.treeError = err.message;
        this.loaded = true;
        this.renderTree();
      })
      .finally(() => {
        this.refreshing = null;
      });
    return this.refreshing;
  }

  renderTree() {
    const { rows, matches, parents } = flattenTree(this.screens, {
      showFramework: this.showFramework,
      query: this.query,
      collapsed: this.collapsed,
    });
    this.rows = rows.filter((row) => row.type === "node");
    this.parents = parents;
    const scroll = this.tree.scrollTop;
    this.tree.textContent = "";

    if (!this.app.targetId) {
      this.tree.appendChild(Panel.empty("No app is connected", "Open the browser preview or connect a device (see Connect)."));
    } else if (this.treeError && !this.screens.length) {
      this.tree.appendChild(Panel.empty("Couldn't read the component tree", this.treeError));
    } else if (!this.loaded) {
      this.tree.appendChild(Panel.empty("Loading the component tree..."));
    } else if (!rows.length) {
      this.tree.appendChild(
        this.query ? Panel.empty("No matches", `Nothing in the tree matches "${this.query}".`) : Panel.empty("Nothing is mounted", "The app has no live screens yet."),
      );
    }

    const fragment = document.createDocumentFragment();
    for (const row of rows) {
      if (row.type === "screen") {
        fragment.appendChild(h("div.tree-screen", { role: "presentation" }, row.screen));
        continue;
      }
      fragment.appendChild(this.rowElement(row));
    }
    this.tree.appendChild(fragment);
    this.tree.scrollTop = scroll;

    const count = this.rows.length;
    const parts = [];
    if (this.loaded && this.app.targetId) parts.push(`${count} node${count === 1 ? "" : "s"}`);
    if (this.query) parts.push(`${matches} match${matches === 1 ? "" : "es"}`);
    if (this.treeError && this.screens.length) parts.push(`refresh failed: ${this.treeError}`);
    this.status.textContent = parts.join(" · ");
  }

  rowElement(row) {
    const node = row.node;
    const selected = row.id === this.selectedId;
    const el = h(
      "div.tree-row",
      {
        role: "treeitem",
        "aria-level": String(row.depth + 1),
        "aria-selected": String(selected),
        "aria-expanded": row.hasChildren ? String(row.expanded) : null,
        dataset: { id: String(row.id) },
        style: { paddingLeft: `${row.depth * 14 + 4}px` },
        title: node.source ? `${node.source.file}:${node.source.line}` : node.tag != null ? `view #${node.tag}` : null,
      },
      h(`span.twisty${row.hasChildren ? ".has-children" : ""}${row.expanded ? ".open" : ""}`, { "aria-hidden": "true" }),
      h(`span.node-name.kind-${node.kind}${row.match ? ".match" : ""}`, null, node.name || "?"),
    );
    if (selected) el.classList.add("selected");
    if (KIND_BADGES[node.kind]) el.appendChild(h("span.node-badge", null, KIND_BADGES[node.kind]));
    if (node.framework) el.appendChild(h("span.node-badge.node-badge-framework", null, "framework"));
    if (node.key != null) el.appendChild(h("span.node-key", null, h("span.attr", null, "key"), "=", h("span.v-str", null, node.key)));
    if (node.text) el.appendChild(h("span.node-text", null, `"${node.text}"`));
    if (node.error) el.appendChild(h("span.node-error", { title: node.error }, "error"));
    return el;
  }

  rowEl(id) {
    return this.tree.querySelector(`.tree-row[data-id="${id}"]`);
  }

  toggle(id, open = null) {
    const row = this.rows.find((r) => r.id === id);
    if (!row || !row.hasChildren || this.query) return;
    const next = open ?? !row.expanded;
    if (next) this.collapsed.delete(id);
    else this.collapsed.add(id);
    this.renderTree();
  }

  onTreeClick(event) {
    const row = event.target.closest(".tree-row");
    if (!row) return;
    const id = Number(row.dataset.id);
    if (event.target.closest(".twisty")) {
      this.toggle(id);
      return;
    }
    this.select(id);
  }

  onTreeKey(event) {
    if (!this.rows.length) return;
    const index = this.rows.findIndex((r) => r.id === this.selectedId);
    const row = this.rows[index];
    let next = null;
    switch (event.key) {
      case "ArrowDown":
        next = this.rows[Math.min(this.rows.length - 1, index + 1)];
        break;
      case "ArrowUp":
        next = this.rows[Math.max(0, index - 1)];
        break;
      case "Home":
        next = this.rows[0];
        break;
      case "End":
        next = this.rows[this.rows.length - 1];
        break;
      case "ArrowRight":
        if (row?.hasChildren && !row.expanded) this.toggle(row.id, true);
        else if (row?.expanded) next = this.rows[index + 1];
        break;
      case "ArrowLeft":
        if (row?.expanded && !this.query) this.toggle(row.id, false);
        else if (row) {
          const parent = this.parents.get(row.id);
          if (parent != null) next = this.rows.find((r) => r.id === parent);
        }
        break;
      case "Enter":
        if (row?.node.source) this.app.openInEditor(row.node.source.file, row.node.source.line);
        break;
      default:
        return;
    }
    event.preventDefault();
    if (index < 0 && !next) next = this.rows[0];
    if (next) this.select(next.id, { debounce: true });
  }

  select(id, { debounce: deferred = false, reveal = false } = {}) {
    this.selectedId = id;
    for (const el of this.tree.querySelectorAll(".tree-row.selected")) {
      el.classList.remove("selected");
      el.setAttribute("aria-selected", "false");
    }
    const el = this.rowEl(id);
    if (el) {
      el.classList.add("selected");
      el.setAttribute("aria-selected", "true");
      el.scrollIntoView({ block: reveal ? "center" : "nearest" });
    }
    this.sendHighlight(id);
    if (deferred) this.inspectSoon(id);
    else this.inspect(id);
  }

  /** The on-device inspector chose a node: reveal it here. */
  async onDeviceSelect(data) {
    // Prefer the view that was tapped; its owner component is one step up.
    const id = data.native_id ?? data.id;
    if (id == null) return;
    this.app.selectTab(this.id);
    if (!pathTo(this.screens, id)) await this.refresh(true);
    const found = revealTarget(this.screens, id, { showFramework: this.showFramework, fallbackId: data.id ?? null });
    if (!found) return;
    if (this.query) {
      this.query = "";
      this.search.value = "";
    }
    for (const id of found.ancestors) this.collapsed.delete(id);
    this.renderTree();
    this.select(found.id, { reveal: true });
    this.tree.focus({ preventScroll: true });
  }

  sendHighlight(id) {
    if (!this.app.targetId || this.app.conn.state !== "open") return;
    this.app.rpc("highlight", { id: id ?? null }).catch(() => {});
  }

  // -- element inspector toggle ------------------------------------------------------

  setInspecting(on) {
    this.inspecting = on;
    this.inspectButton.setAttribute("aria-pressed", String(on));
    this.inspectButton.classList.toggle("on", on);
    this.inspectButton.title = on ? "Stop selecting elements on the device" : "Select an element on the device to inspect it";
  }

  async toggleInspecting() {
    if (!this.app.targetId) return;
    const next = !this.inspecting;
    this.setInspecting(next);
    try {
      const result = await this.app.rpc("set_inspecting", { enabled: next });
      this.setInspecting(!!result);
      if (result) this.app.toast(`Click or tap an element in ${this.app.targetLabel(this.app.targetId)}`);
    } catch (err) {
      this.setInspecting(!next);
      this.app.toast(`Couldn't toggle the inspector: ${err.message}`, "error");
    }
  }

  // -- inspector ------------------------------------------------------------------

  editing() {
    return !!this.inspector.querySelector(".hook-editor");
  }

  async inspect(id, { quiet = false } = {}) {
    const seq = ++this.inspectSeq;
    const target = this.app.targetId;
    if (!quiet) this.inspector.classList.add("loading");
    try {
      const result = await this.app.rpc("inspect", { id });
      if (seq !== this.inspectSeq || target !== this.app.targetId) return;
      this.inspected = result;
      this.inspectError = null;
    } catch (err) {
      if (seq !== this.inspectSeq) return;
      if (quiet && this.inspected?.id === id) this.inspected = { ...this.inspected, stale: true };
      else {
        this.inspected = null;
        this.inspectError = err.message;
      }
    } finally {
      if (seq === this.inspectSeq) this.inspector.classList.remove("loading");
    }
    this.renderInspector();
  }

  renderInspector() {
    const box = this.inspector;
    box.textContent = "";
    const data = this.inspected;
    if (!data) {
      box.appendChild(
        this.inspectError
          ? Panel.empty("Couldn't inspect that node", this.inspectError)
          : Panel.empty("Select a component", "Pick a node in the tree, or use the arrow button to pick one on the device."),
      );
      return;
    }

    const header = h(
      "div.inspector-header",
      null,
      h(`span.inspector-name.kind-${data.kind}`, null, data.name || "?"),
      KIND_BADGES[data.kind] ? h("span.node-badge", null, KIND_BADGES[data.kind]) : null,
      data.kind === "native" ? h("span.node-badge", null, "view") : null,
      h("span.spacer"),
      h(
        "button.btn.btn-small",
        { type: "button", title: "Use this component as `node` in the console", onclick: () => this.app.panels.find((p) => p.id === "console")?.useNode() },
        "Use in console",
      ),
    );
    box.appendChild(header);
    if (data.stale) box.appendChild(h("div.notice", null, "This node is no longer mounted; showing its last state."));

    const meta = h("div.inspector-meta");
    if (data.source?.file) {
      meta.appendChild(
        h(
          "button.link.source-link",
          { type: "button", title: "Open in your editor", onclick: () => this.app.openInEditor(data.source.file, data.source.line) },
          icon("open", 12),
          `${data.source.file}:${data.source.line}`,
        ),
      );
    }
    if (data.key) meta.appendChild(h("span.meta-item", null, "key ", h("span.v-str", null, valueText(data.key))));
    if (data.tag != null) meta.appendChild(h("span.meta-item", null, `view #${data.tag}`));
    if (meta.childElementCount) box.appendChild(meta);

    if (Array.isArray(data.path) && data.path.length) {
      const crumbs = h("nav.breadcrumbs", { "aria-label": "Component path" });
      data.path.forEach((name, index) => {
        if (index) crumbs.appendChild(h("span.crumb-sep", { "aria-hidden": "true" }, "›"));
        crumbs.appendChild(h(index === data.path.length - 1 ? "span.crumb.current" : "span.crumb", null, name));
      });
      box.appendChild(crumbs);
    }

    if (data.error) box.appendChild(this.section("Error", h("pre.inspector-error", null, data.error)));

    const props = Object.entries(data.props || {});
    box.appendChild(
      this.section("Props", props.length ? props.map(([key, summary]) => valueRow(key, summary)) : h("div.none", null, "No props")),
    );

    if (data.value) box.appendChild(this.section("Provided value", valueRow(null, data.value)));
    if (Array.isArray(data.hooks) && data.hooks.length) box.appendChild(this.section("Hooks", data.hooks.map((hook) => this.hookRow(hook, data.id))));
    if (Array.isArray(data.context) && data.context.length) {
      box.appendChild(this.section("Context", data.context.map((summary, index) => valueRow(String(index), summary))));
    }
    if (data.frame) {
      const f = data.frame;
      const round = (n) => Math.round(Number(n) * 10) / 10;
      box.appendChild(
        this.section(
          "Layout",
          h(
            "div.layout-grid",
            null,
            ["x", "y", "width", "height"].map((k) => h("div.layout-cell", null, h("span.layout-key", null, k), h("span.v-num", null, String(round(f[k]))))),
          ),
        ),
      );
    }
  }

  section(title, body) {
    const open = prefs.get(`section:${title}`, true);
    const details = h("details.section", { open }, h("summary.section-title", null, title), h("div.section-body", null, body));
    details.addEventListener("toggle", () => prefs.set(`section:${title}`, details.open));
    return details;
  }

  hookRow(hook, nodeId) {
    const name = HOOK_NAMES[hook.hook] || hook.hook || "hook";
    const position = hook.position ?? hook.index;
    const prefix = position != null ? h("span.hook-index", { title: "Hook position" }, String(position)) : null;
    const valueNode = hook.editable && hook.value ? this.editableValue(hook, nodeId) : null;
    const wrap = h("div.hook");
    if (hook.value) wrap.appendChild(valueRow(name, hook.value, { prefix, valueNode }));
    else wrap.appendChild(h("div.value-row", { style: { paddingLeft: "4px" } }, h("span.twisty"), prefix, h("span.value-key", null, name)));
    if (hook.deps) wrap.appendChild(valueRow("deps", hook.deps, { depth: 1 }));
    return wrap;
  }

  editableValue(hook, nodeId) {
    const summary = hook.value;
    const save = async (source, field) => {
      try {
        await this.app.rpc("set_state", { id: nodeId, index: hook.index, value: source });
        setTimeout(() => {
          this.inspect(nodeId, { quiet: true });
          this.refresh(false);
        }, 120);
        return true;
      } catch (err) {
        if (field) {
          field.classList.add("invalid");
          field.title = err.message;
        }
        this.app.toast(`Couldn't set state: ${err.message}`, "error");
        return false;
      }
    };

    if (summary.type === "bool") {
      const box = h("input.hook-bool", { type: "checkbox", checked: summary.repr === "True", title: "Toggle this state value" });
      box.addEventListener("change", () => save(box.checked ? "True" : "False", null));
      return h("span.value-edit", null, box, h(`span.value-text.v-const`, null, summary.repr));
    }

    const literal = summary.source ?? (summary.literal ? summary.repr : null);
    const text = h(`span.value-text.editable.${summary.type === "str" ? "v-str" : summary.type === "int" || summary.type === "float" ? "v-num" : "v-obj"}`, {
      tabIndex: 0,
      role: "button",
      title: literal != null ? "Click to edit (a Python literal)" : "Click to replace with a Python literal",
    }, valueText(summary));
    const container = h("span.value-edit", null, text, icon("edit", 11));
    const startEdit = (event) => {
      event?.stopPropagation();
      const field = h("input.hook-editor", { type: "text", spellcheck: "false", value: literal ?? "", "aria-label": "New value (Python literal)" });
      container.replaceChildren(field);
      field.focus();
      field.select();
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        container.replaceChildren(text, icon("edit", 11));
      };
      field.addEventListener("keydown", async (e) => {
        e.stopPropagation();
        if (e.key === "Escape") finish();
        else if (e.key === "Enter") {
          e.preventDefault();
          if (await save(field.value, field)) finish();
        }
      });
      field.addEventListener("input", () => field.classList.remove("invalid"));
      field.addEventListener("blur", () => setTimeout(finish, 100));
      field.addEventListener("click", (e) => e.stopPropagation());
    };
    text.addEventListener("click", startEdit);
    text.addEventListener("keydown", (event) => {
      if (event.key === "Enter") startEdit(event);
    });
    return container;
  }
}
