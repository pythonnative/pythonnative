// PythonNative DevTools: the page `pn start` serves at `/devtools`
// (RFC 0006). It talks to the dev server over `/ws?role=devtools`; the
// server routes requests to the selected target's devtools agent (the
// browser preview or a connected dev client) and broadcasts every
// target's events here.

import { Connection } from "./connection.js";
import { h, icon, kindBadge, prefs, typing } from "./util.js";
import { ComponentsPanel } from "./panels/components.js";
import { ConsolePanel } from "./panels/console.js";
import { ProblemsPanel } from "./panels/problems.js";
import { NetworkPanel } from "./panels/network.js";
import { PerformancePanel } from "./panels/performance.js";
import { ConnectPanel } from "./panels/connect.js";

const $ = (id) => document.getElementById(id);

export class App {
  constructor() {
    this.targets = [];
    this.labels = new Map(); // target id -> label, kept after disconnects
    this.targetId = null;
    this.debugTarget = null;
    this.debugAttached = null; // target id with a live debugger session
    this.connectDoc = null;
    this.project = "";
    this.remembered = prefs.get("target", null); // {id, label, kind}

    const scheme = location.protocol === "https:" ? "wss" : "ws";
    this.conn = new Connection(`${scheme}://${location.host}/ws?role=devtools`);

    this.panels = [
      new ComponentsPanel(this),
      new ConsolePanel(this),
      new ProblemsPanel(this),
      new NetworkPanel(this),
      new PerformancePanel(this),
      new ConnectPanel(this),
    ];
    this.active = null;

    this.buildChrome();
    this.listen();
    this.selectTab(prefs.get("tab", "components"));
    this.conn.connect();
  }

  // -- chrome -------------------------------------------------------------

  buildChrome() {
    this.targetSelect = $("target-select");
    this.targetSelect.addEventListener("change", () => this.selectTarget(this.targetSelect.value || null, { explicit: true }));
    $("reload-button").addEventListener("click", () => this.reloadTarget());
    $("menu-button").addEventListener("click", () => this.openMenu());
    $("debug-button").addEventListener("click", () => this.debugThisApp());
    $("retry-button").addEventListener("click", () => this.conn.reconnectNow());

    const tabs = $("tabs");
    this.tabButtons = new Map();
    this.panels.forEach((panel, index) => {
      const badge = h("span.tab-badges");
      const button = h(
        "button.tab",
        {
          type: "button",
          role: "tab",
          id: `tab-${panel.id}`,
          "aria-controls": `panel-${panel.id}`,
          "aria-selected": "false",
          tabIndex: -1,
          title: `${panel.title} (Alt+${index + 1})`,
          onclick: () => this.selectTab(panel.id),
        },
        h("span", null, panel.title),
        badge,
      );
      button._badge = badge;
      tabs.appendChild(button);
      this.tabButtons.set(panel.id, button);
      panel.el.id = `panel-${panel.id}`;
      panel.el.setAttribute("role", "tabpanel");
      panel.el.setAttribute("aria-labelledby", `tab-${panel.id}`);
      panel.el.classList.add("panel");
      panel.el.hidden = true;
      $("panels").appendChild(panel.el);
    });
    tabs.addEventListener("keydown", (event) => {
      const ids = this.panels.map((p) => p.id);
      const index = ids.indexOf(this.active?.id);
      let next = null;
      if (event.key === "ArrowRight") next = ids[(index + 1) % ids.length];
      else if (event.key === "ArrowLeft") next = ids[(index - 1 + ids.length) % ids.length];
      else if (event.key === "Home") next = ids[0];
      else if (event.key === "End") next = ids[ids.length - 1];
      if (!next) return;
      event.preventDefault();
      this.selectTab(next);
      this.tabButtons.get(next).focus();
    });

    document.addEventListener("keydown", (event) => {
      if (event.altKey && !event.metaKey && !event.ctrlKey && /^Digit[1-9]$/.test(event.code)) {
        const panel = this.panels[Number(event.code.slice(5)) - 1];
        if (panel) {
          event.preventDefault();
          this.selectTab(panel.id);
        }
        return;
      }
      if (event.key === "/" && !typing(event) && !event.metaKey && !event.ctrlKey) {
        if (this.active?.focusSearch?.()) event.preventDefault();
      }
    });
    window.addEventListener("pagehide", () => this.panels.forEach((panel) => panel.onPageHide?.()));
  }

  selectTab(id) {
    const panel = this.panels.find((p) => p.id === id) || this.panels[0];
    if (this.active === panel) return;
    const previous = this.active;
    this.active = panel;
    for (const [pid, button] of this.tabButtons) {
      const on = pid === panel.id;
      button.setAttribute("aria-selected", String(on));
      button.tabIndex = on ? 0 : -1;
      button.classList.toggle("active", on);
    }
    if (previous) {
      previous.el.hidden = true;
      previous.onHide?.();
    }
    panel.el.hidden = false;
    panel.onShow?.();
    prefs.set("tab", panel.id);
  }

  /** Refresh one tab's badges from `panel.badges()` → `[{text, cls}]`. */
  updateBadges(panel) {
    const button = this.tabButtons.get(panel.id);
    if (!button) return;
    const badges = panel.badges?.() || [];
    button._badge.textContent = "";
    for (const badge of badges) button._badge.appendChild(h(`span.badge.${badge.cls}`, null, String(badge.text)));
  }

  // -- connection -----------------------------------------------------------

  listen() {
    const conn = this.conn;
    conn.on("state", (state) => this.onConnectionState(state));
    conn.on("targets", (message) => this.onTargets(message));
    conn.on("history", (message) => {
      for (const panel of this.panels) panel.onHistoryStart?.();
      for (const event of message.events || []) this.dispatchEvent(event, true);
      for (const panel of this.panels) panel.onHistoryEnd?.();
    });
    conn.on("event", (event) => this.dispatchEvent(event, false));
    conn.on("connect", (message) => this.onConnectDoc(message));
    conn.on("debug", (message) => {
      this.debugAttached = message.state === "attached" ? message.target : null;
      this.renderDebugger();
      const label = this.targetLabel(message.target);
      for (const panel of this.panels) panel.onDebug?.(message);
      this.panels.find((p) => p.id === "console")?.system(
        message.state === "attached" ? `Debugger attached to ${label}` : `Debugger detached from ${label}`,
      );
    });
    conn.on("opened", (message) => {
      if (message.error) this.toast(message.error, "error");
      else this.toast(`Opened ${message.path || message.file}`);
    });
  }

  onConnectionState(state) {
    const dot = $("status-dot");
    dot.dataset.state = state;
    dot.title = state === "open" ? "Connected to pn start" : state === "connecting" ? "Connecting to pn start" : "Disconnected from pn start";
    $("status-text").textContent = state === "open" ? "Connected" : state === "connecting" ? "Connecting" : "Disconnected";
    const banner = $("banner");
    if (state === "open") {
      banner.hidden = true;
      this.conn.send({ type: "connect" });
    } else if (state === "closed") {
      banner.hidden = false;
      $("banner-text").textContent = this.conn.everOpened
        ? "Lost the connection to pn start. Reconnecting..."
        : "Can't reach pn start. Is it running? Retrying...";
      if (!this.conn.everOpened) this.explainRefusal();
    }
    this.renderTargetSelect(this.targetId);
    for (const panel of this.panels) panel.onConnection?.(state);
  }

  // The socket needs the dev token cookie, which the page gets when it's
  // opened from the URL `pn start` printed. Browsers hide why a WebSocket
  // upgrade failed, so ask `/status`.
  async explainRefusal() {
    try {
      const response = await fetch("/status", { cache: "no-store" });
      if (response.status === 401 || response.status === 403) {
        $("banner-text").textContent =
          "This page doesn't have the dev token. Open the DevTools URL that pn start printed (it ends in ?token=...), or press j in its terminal.";
      }
    } catch (err) {
      /* the server is down; the default message applies */
    }
  }

  onConnectDoc(doc) {
    this.connectDoc = doc;
    this.project = doc.project || "";
    $("project-name").textContent = this.project;
    document.title = this.project ? `${this.project} · PythonNative DevTools` : "PythonNative DevTools";
    this.renderDebugger();
    for (const panel of this.panels) panel.onConnectDoc?.(doc);
  }

  dispatchEvent(event, replay) {
    if (!event || typeof event !== "object") return;
    for (const panel of this.panels) panel.onEvent?.(event, replay);
  }

  // -- targets ----------------------------------------------------------------

  onTargets(message) {
    this.targets = Array.isArray(message.targets) ? message.targets : [];
    this.debugTarget = message.debug_target || null;
    for (const target of this.targets) this.labels.set(target.id, target.label || target.id);

    let next = this.targetId && this.targets.some((t) => t.id === this.targetId) ? this.targetId : null;
    const remembered = this.remembered;
    if (!next && remembered) {
      // A reconnecting device gets a new id; follow it by label and kind.
      const same =
        this.targets.find((t) => t.id === remembered.id) ||
        this.targets.find((t) => t.label === remembered.label && t.kind === remembered.kind);
      if (same) next = same.id;
    }
    if (!next && this.targets.length) next = this.targets[0].id;

    this.renderTargetSelect(next);
    for (const panel of this.panels) panel.onTargets?.(this.targets);
    if (next !== this.targetId) this.selectTarget(next);
    this.renderDebugger();
  }

  renderTargetSelect(selected) {
    const select = this.targetSelect;
    select.textContent = "";
    if (!this.targets.length) {
      select.appendChild(h("option", { value: "" }, "No app connected"));
      select.disabled = true;
    } else {
      select.disabled = false;
      for (const target of this.targets) {
        const badge = kindBadge(target.kind);
        select.appendChild(h("option", { value: target.id }, `${target.label || target.id}  [${badge.text}]`));
      }
      select.value = selected || "";
    }
    const target = this.targets.find((t) => t.id === selected);
    const kind = $("target-kind");
    if (target) {
      const badge = kindBadge(target.kind);
      kind.className = `badge ${badge.cls}`;
      kind.textContent = badge.text;
      kind.hidden = false;
    } else {
      kind.hidden = true;
    }
    const live = !!target && this.conn.state === "open";
    for (const id of ["reload-button", "menu-button", "debug-button"]) $(id).disabled = !live;
  }

  selectTarget(id, { explicit = false } = {}) {
    const previous = this.targetId;
    this.targetId = id || null;
    const target = this.target();
    if (target && (explicit || !this.remembered)) {
      this.remembered = { id: target.id, label: target.label, kind: target.kind };
      prefs.set("target", this.remembered);
    }
    this.renderTargetSelect(this.targetId);
    this.renderDebugger();
    if (previous !== this.targetId) for (const panel of this.panels) panel.onTarget?.(target, previous);
  }

  target() {
    return this.targets.find((t) => t.id === this.targetId) || null;
  }

  targetLabel(id) {
    if (!id) return "";
    return this.labels.get(id) || id;
  }

  /** Call the selected target's agent. */
  rpc(method, params = {}, options = {}) {
    return this.conn.rpc(this.targetId, method, params, options);
  }

  // -- header actions ------------------------------------------------------------

  reloadTarget() {
    if (!this.targetId) return;
    this.conn.send({ type: "command", name: "reload", target: this.targetId });
    this.toast(`Reloading ${this.targetLabel(this.targetId)}`);
  }

  async openMenu() {
    if (!this.targetId) return;
    try {
      await this.rpc("menu");
      this.toast(`Opened the dev menu on ${this.targetLabel(this.targetId)}`);
    } catch (err) {
      this.toast(`Couldn't open the dev menu: ${err.message}`, "error");
    }
  }

  debugThisApp() {
    if (!this.targetId) return;
    this.conn.send({ type: "debug_target", target: this.targetId });
  }

  /** The target a debugger attaches to: the chosen one, else the newest device, else the preview. */
  effectiveDebugTarget() {
    if (this.debugTarget && this.targets.some((t) => t.id === this.debugTarget)) return this.debugTarget;
    const clients = this.targets.filter((t) => t.kind !== "preview");
    if (clients.length) return clients.reduce((a, b) => ((b.connected_at || 0) > (a.connected_at || 0) ? b : a)).id;
    return this.targets.find((t) => t.kind === "preview")?.id || null;
  }

  renderDebugger() {
    const chip = $("debug-chip");
    const button = $("debug-button");
    const port = this.connectDoc?.debug_port;
    const target = this.effectiveDebugTarget();
    const attached = this.debugAttached;
    chip.dataset.state = attached ? "attached" : target ? "ready" : "none";
    const label = $("debug-label");
    if (port === 0) {
      label.textContent = "Debugger off";
      chip.title = "pn start was started with --debug-port 0";
    } else if (attached) {
      label.textContent = `Debugging ${this.targetLabel(attached)}`;
      chip.title = "A debugger is attached";
    } else if (target) {
      label.textContent = `Debugger → ${this.targetLabel(target)}`;
      chip.title = `VS Code's 'PythonNative: Attach' (127.0.0.1:${port || 5678}) debugs ${this.targetLabel(target)}`;
    } else {
      label.textContent = "Debugger";
      chip.title = "No app is connected";
    }
    const isTarget = !!this.targetId && this.targetId === target;
    button.hidden = !this.targetId || isTarget || port === 0;
    button.title = `Attach the debugger to ${this.targetLabel(this.targetId)} instead`;
  }

  // -- feedback ---------------------------------------------------------------

  toast(text, kind = "info") {
    const host = $("toasts");
    const toast = h(`div.toast.toast-${kind}`, { role: kind === "error" ? "alert" : "status" }, String(text));
    host.appendChild(toast);
    setTimeout(() => toast.classList.add("leaving"), kind === "error" ? 5000 : 2200);
    setTimeout(() => toast.remove(), kind === "error" ? 5400 : 2600);
  }

  /** Ask `pn start` to open `file:line` in the developer's editor. */
  openInEditor(file, line) {
    if (!file) return;
    if (!this.conn.send({ type: "open", file, line: Number(line) || 1 })) this.toast("Not connected to pn start", "error");
  }
}

// Icons in the static header markup.
for (const node of document.querySelectorAll("[data-icon]")) node.prepend(icon(node.dataset.icon));

window.pnDevTools = new App();
