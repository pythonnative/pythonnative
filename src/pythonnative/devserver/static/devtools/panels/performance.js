// Performance: live numbers from the selected app's sampler (one `perf`
// event a second while this panel is open), sparklines over the last
// minute, recent commits, a phase breakdown, the on-device monitor, and
// Chrome trace recording.

import { Panel } from "./panel.js";
import { clock, downloadJSON, formatBytes, formatMs, h, icon } from "../util.js";

const WINDOW = 60;

/** Per-second rates and headline numbers for one sample. */
export function sampleMetrics(sample) {
  const seconds = Math.max(0.001, Number(sample?.interval_s) || 1);
  const phases = sample?.phases || {};
  const commits = Array.isArray(sample?.commits) ? sample.commits : [];
  const commit = phases.commit || {};
  return {
    fps: sample?.ui_fps == null ? null : Number(sample.ui_fps),
    dropped: sample?.ui_dropped == null ? null : Number(sample.ui_dropped),
    lag: Number(sample?.loop_lag_ms) || 0,
    renders: (Number(phases.render?.count) || 0) / seconds,
    commits: (Number(commit.count) || 0) / seconds,
    commitMax: Number(commit.max_ms) || 0,
    commitLast: commits.length ? Number(commits[commits.length - 1].ms) || 0 : null,
    components: (Number(sample?.components_rendered) || 0) / seconds,
    operations: (Number(sample?.bridge_operations) || 0) / seconds,
    bytes: (Number(sample?.bridge_bytes) || 0) / seconds,
  };
}

/** SVG path data (`line`, `area`) for values on a `width` x `height` box. */
export function sparkPath(values, width, height, max = null) {
  const points = values.map((v) => (v == null || !Number.isFinite(v) ? null : v));
  const finite = points.filter((v) => v != null);
  if (!finite.length) return { line: "", area: "", max: 0 };
  const top = max ?? Math.max(...finite, 1e-9);
  const step = values.length > 1 ? width / (WINDOW - 1) : 0;
  const offset = width - step * (values.length - 1);
  const y = (v) => height - 1 - (Math.min(v, top) / top) * (height - 2);
  let line = "";
  let started = false;
  points.forEach((v, i) => {
    if (v == null) {
      started = false;
      return;
    }
    const x = (offset + i * step).toFixed(1);
    line += `${started ? "L" : "M"}${x},${y(v).toFixed(1)}`;
    started = true;
  });
  const firstX = (offset + points.findIndex((v) => v != null) * step).toFixed(1);
  const lastIndex = points.length - 1 - [...points].reverse().findIndex((v) => v != null);
  const lastX = (offset + lastIndex * step).toFixed(1);
  const area = `${line}L${lastX},${height}L${firstX},${height}Z`;
  return { line, area, max: top };
}

const TILES = [
  { key: "fps", title: "UI frame rate", unit: "fps", max: 60, format: (v) => Math.round(v), hint: "Native frames per second (devices only)" },
  { key: "lag", title: "Loop lag", unit: "ms", format: (v) => v.toFixed(v < 10 ? 1 : 0), hint: "How late the application loop runs scheduled work" },
  { key: "renders", title: "Renders", unit: "/s", format: (v) => v.toFixed(v < 10 ? 1 : 0), hint: "Render passes per second" },
  { key: "commits", title: "Commits", unit: "/s", format: (v) => v.toFixed(v < 10 ? 1 : 0), hint: "Commits to the native views per second" },
  { key: "commitMax", title: "Slowest commit", unit: "ms", format: (v) => v.toFixed(v < 10 ? 2 : 1), hint: "The longest commit in each second" },
  { key: "components", title: "Components", unit: "/s", format: (v) => Math.round(v), hint: "Component functions run per second" },
  { key: "operations", title: "Bridge ops", unit: "/s", format: (v) => Math.round(v), hint: "View operations sent to native per second" },
  { key: "bytes", title: "Bridge data", unit: "", format: (v) => `${formatBytes(Math.round(v)) || "0 B"}/s`, hint: "Bytes sent to native per second" },
];

export class PerformancePanel extends Panel {
  constructor(app) {
    super(app, "performance", "Performance");
    this.samples = new Map(); // target id -> samples (oldest first)
    this.enabledOn = null; // target the panel turned sampling on for
    this.monitor = false;
    this.recording = null; // {target, started}
    this.build();
  }

  build() {
    this.el.classList.add("performance");
    this.monitorToggle = h("input", { type: "checkbox" });
    this.monitorToggle.addEventListener("change", () => this.setMonitor(this.monitorToggle.checked));
    this.recordButton = h("button.btn", { type: "button", onclick: () => this.toggleTrace() });
    this.recordNote = h("span.toolbar-note");
    this.state = h("span.toolbar-note");
    this.el.append(
      h(
        "div.toolbar",
        null,
        this.recordButton,
        this.recordNote,
        h("span.toolbar-sep"),
        h("label.check", { title: "Show the floating performance monitor on the app" }, this.monitorToggle, "On-device monitor"),
        h("span.spacer"),
        this.state,
      ),
    );
    this.tiles = h("div.tiles");
    this.tileEls = new Map();
    for (const tile of TILES) {
      const value = h("span.tile-value");
      const unit = h("span.tile-unit", null, tile.unit);
      const spark = h("div.spark");
      const el = h(
        "div.tile",
        { title: tile.hint },
        h("div.tile-title", null, tile.title),
        h("div.tile-number", null, value, unit),
        spark,
      );
      this.tileEls.set(tile.key, { el, value, unit, spark });
      this.tiles.appendChild(el);
    }
    this.commitsBody = h("tbody");
    this.phasesBody = h("tbody");
    this.content = h(
      "div.perf-content",
      null,
      this.tiles,
      h(
        "div.perf-tables",
        null,
        h(
          "section.perf-table",
          null,
          h("h3.perf-heading", null, "Recent commits"),
          h("div.grid-wrap", null, h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Time"), h("th.num", null, "Duration"), h("th", null, ""))), this.commitsBody)),
        ),
        h(
          "section.perf-table",
          null,
          h("h3.perf-heading", null, "Phases (last 10 s)"),
          h(
            "div.grid-wrap",
            null,
            h(
              "table.grid",
              null,
              h("thead", null, h("tr", null, h("th", null, "Phase"), h("th.num", null, "Count"), h("th.num", null, "Total"), h("th.num", null, "Average"), h("th.num", null, "Max"))),
              this.phasesBody,
            ),
          ),
        ),
      ),
    );
    this.emptyEl = h("div");
    this.el.append(this.emptyEl, this.content);
    this.renderRecord();
    this.render();
  }

  // -- sampling control -----------------------------------------------------------

  onShow() {
    super.onShow();
    this.sync();
    this.render();
  }

  onHide() {
    super.onHide();
    this.sync();
  }

  onTarget(target, previous) {
    if (this.recording && this.recording.target === previous) this.recording = null;
    this.monitor = false;
    this.monitorToggle.checked = false;
    this.sync();
    this.renderRecord();
    this.render();
    if (target) {
      this.app
        .rpc("status")
        .then((status) => {
          if (this.app.targetId !== target.id) return;
          this.monitor = !!status?.perf_monitor;
          this.monitorToggle.checked = this.monitor;
        })
        .catch(() => {});
    }
  }

  onConnection(state) {
    if (state !== "open") this.enabledOn = null;
    else this.sync();
  }

  onPageHide() {
    if (this.enabledOn) this.app.conn.rpc(this.enabledOn, "perf", { enabled: false }).catch(() => {});
  }

  /** Sampling is on for the selected app exactly while this panel is visible. */
  sync() {
    const want = this.visible && this.app.conn.state === "open" ? this.app.targetId : null;
    if (want === this.enabledOn) return;
    const previous = this.enabledOn;
    this.enabledOn = want;
    if (previous && this.app.targets.some((t) => t.id === previous)) {
      this.app.conn.rpc(previous, "perf", { enabled: false }).catch(() => {});
    }
    if (want) {
      this.app.conn
        .rpc(want, "perf", { enabled: true })
        .then((result) => {
          if (want !== this.app.targetId) return;
          this.monitor = !!result?.monitor;
          this.monitorToggle.checked = this.monitor;
        })
        .catch((err) => {
          if (this.enabledOn === want) this.enabledOn = null;
          this.state.textContent = `Couldn't start sampling: ${err.message}`;
        });
    }
  }

  async setMonitor(on) {
    if (!this.app.targetId) return;
    try {
      const result = await this.app.rpc("perf", { enabled: this.visible, monitor: on });
      this.monitor = !!result?.monitor;
    } catch (err) {
      this.app.toast(`Couldn't toggle the monitor: ${err.message}`, "error");
    }
    this.monitorToggle.checked = this.monitor;
  }

  // -- events ---------------------------------------------------------------------

  onHistoryStart() {
    this.samples = new Map();
  }

  onEvent(event) {
    if (event.topic === "perf_monitor" && event.target === this.app.targetId) {
      this.monitor = !!event.data?.visible;
      this.monitorToggle.checked = this.monitor;
      return;
    }
    if (event.topic !== "perf" || !event.data) return;
    const list = this.samples.get(event.target) || [];
    list.push(event.data);
    if (list.length > WINDOW * 2) list.splice(0, list.length - WINDOW * 2);
    this.samples.set(event.target, list);
    if (event.target === this.app.targetId && this.visible) this.render();
  }

  // -- trace --------------------------------------------------------------------

  async toggleTrace() {
    const target = this.app.targetId;
    if (!target) return;
    if (!this.recording) {
      try {
        await this.app.rpc("trace", { action: "start" });
        this.recording = { target, started: Date.now() };
        this.recordTimer = setInterval(() => this.renderRecord(), 500);
      } catch (err) {
        this.app.toast(`Couldn't start a trace: ${err.message}`, "error");
      }
      this.renderRecord();
      return;
    }
    const recording = this.recording;
    this.recording = null;
    clearInterval(this.recordTimer);
    this.recordButton.disabled = true;
    try {
      const trace = await this.app.conn.rpc(recording.target, "trace", { action: "stop" }, { timeout: 60000 });
      const stamp = new Date().toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
      const name = `pythonnative-trace-${stamp}.json`;
      downloadJSON(name, trace || { traceEvents: [] });
      const events = Array.isArray(trace?.traceEvents) ? trace.traceEvents.length : 0;
      this.app.toast(`Saved ${name} (${events} events). Open it in ui.perfetto.dev or chrome://tracing.`);
    } catch (err) {
      this.app.toast(`Couldn't stop the trace: ${err.message}`, "error");
    } finally {
      this.recordButton.disabled = false;
      this.renderRecord();
    }
  }

  renderRecord() {
    const button = this.recordButton;
    button.textContent = "";
    button.disabled = !this.app.targetId;
    if (this.recording) {
      button.classList.add("recording");
      button.append(icon("stop", 12), h("span", null, "Stop and save trace"));
      const seconds = Math.floor((Date.now() - this.recording.started) / 1000);
      this.recordNote.textContent = `Recording ${seconds} s`;
    } else {
      button.classList.remove("recording");
      button.append(icon("record", 12), h("span", null, "Record trace"));
      this.recordNote.textContent = "";
    }
  }

  // -- rendering ------------------------------------------------------------------

  render() {
    const target = this.app.targetId;
    const samples = (target && this.samples.get(target)) || [];
    this.emptyEl.textContent = "";
    if (!target) {
      this.content.hidden = true;
      this.emptyEl.appendChild(Panel.empty("No app is connected", "Performance numbers appear for the selected app."));
      this.state.textContent = "";
      return;
    }
    if (!samples.length) {
      this.content.hidden = true;
      this.emptyEl.appendChild(Panel.empty("Waiting for samples...", `${this.app.targetLabel(target)} reports once a second while this panel is open.`));
      return;
    }
    this.content.hidden = false;
    const recent = samples.slice(-WINDOW);
    const metrics = recent.map(sampleMetrics);
    const latest = metrics[metrics.length - 1];
    this.state.textContent = `Updated ${clock(recent[recent.length - 1].time)}`;

    for (const tile of TILES) {
      const parts = this.tileEls.get(tile.key);
      const values = metrics.map((m) => m[tile.key]);
      const value = latest[tile.key];
      const missing = value == null;
      parts.el.classList.toggle("tile-missing", missing);
      parts.value.textContent = missing ? "n/a" : tile.format(value);
      parts.unit.hidden = missing || !tile.unit;
      this.drawSpark(parts.spark, values, tile);
    }

    // Commits: newest first, from the last few samples.
    this.commitsBody.textContent = "";
    const commits = [];
    for (let i = recent.length - 1; i >= 0 && commits.length < 30; i--) {
      const sample = recent[i];
      for (const commit of [...(sample.commits || [])].reverse()) {
        commits.push({ ms: Number(commit.ms) || 0, time: sample.time });
        if (commits.length >= 30) break;
      }
    }
    if (!commits.length) this.commitsBody.appendChild(h("tr", null, h("td.muted", { colSpan: 3 }, "No commits in the last minute")));
    const budget = 16.7;
    for (const commit of commits) {
      const width = Math.min(100, (commit.ms / (budget * 2)) * 100);
      this.commitsBody.appendChild(
        h(
          "tr",
          null,
          h("td", null, clock(commit.time)),
          h("td.num", null, formatMs(commit.ms)),
          h("td.bar-cell", null, h(`span.bar${commit.ms > budget ? ".over" : ""}`, { style: { width: `${Math.max(2, width)}%` }, title: commit.ms > budget ? "Longer than a 60 Hz frame" : "" })),
        ),
      );
    }

    // Phases over the last ten samples.
    const totals = new Map();
    for (const sample of recent.slice(-10)) {
      for (const [name, phase] of Object.entries(sample.phases || {})) {
        const entry = totals.get(name) || { count: 0, total: 0, max: 0 };
        entry.count += Number(phase.count) || 0;
        entry.total += Number(phase.total_ms) || 0;
        entry.max = Math.max(entry.max, Number(phase.max_ms) || 0);
        totals.set(name, entry);
      }
    }
    this.phasesBody.textContent = "";
    const rows = [...totals.entries()].sort((a, b) => b[1].total - a[1].total);
    if (!rows.length) this.phasesBody.appendChild(h("tr", null, h("td.muted", { colSpan: 5 }, "No work recorded")));
    for (const [name, entry] of rows) {
      this.phasesBody.appendChild(
        h(
          "tr",
          null,
          h("td.mono", null, name),
          h("td.num", null, String(entry.count)),
          h("td.num", null, formatMs(entry.total)),
          h("td.num", null, entry.count ? formatMs(entry.total / entry.count) : ""),
          h("td.num", null, formatMs(entry.max)),
        ),
      );
    }
  }

  drawSpark(box, values, tile) {
    const width = 160;
    const height = 32;
    const { line, area, max } = sparkPath(values, width, height, tile.max ?? null);
    const ns = "http://www.w3.org/2000/svg";
    let svg = box.querySelector("svg");
    if (!svg) {
      svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("preserveAspectRatio", "none");
      svg.setAttribute("aria-hidden", "true");
      for (const cls of ["spark-area", "spark-line"]) {
        const path = document.createElementNS(ns, "path");
        path.setAttribute("class", cls);
        svg.appendChild(path);
      }
      box.appendChild(svg);
      const tip = h("div.spark-tip", { hidden: true });
      const cursor = h("div.spark-cursor", { hidden: true });
      box.append(cursor, tip);
      box.addEventListener("mousemove", (event) => {
        const data = box._values || [];
        if (!data.length) return;
        const rect = box.getBoundingClientRect();
        const step = rect.width / (WINDOW - 1);
        const offset = rect.width - step * (data.length - 1);
        const index = Math.max(0, Math.min(data.length - 1, Math.round((event.clientX - rect.left - offset) / step)));
        const value = data[index];
        const x = offset + index * step;
        cursor.hidden = false;
        cursor.style.left = `${x}px`;
        tip.hidden = false;
        const ago = data.length - 1 - index;
        tip.textContent = `${value == null ? "n/a" : `${box._tile.format(value)}${box._tile.unit && box._tile.unit !== "/s" ? ` ${box._tile.unit}` : box._tile.unit}`} · ${ago ? `${ago} s ago` : "now"}`;
        tip.style.left = `${Math.min(Math.max(0, x - 40), rect.width - 90)}px`;
      });
      box.addEventListener("mouseleave", () => {
        cursor.hidden = true;
        tip.hidden = true;
      });
    }
    box._values = values;
    box._tile = tile;
    const [areaPath, linePath] = svg.querySelectorAll("path");
    areaPath.setAttribute("d", area);
    linePath.setAttribute("d", line);
    box.title = max ? `Scale: 0 to ${tile.format(max)}${tile.unit === "/s" ? "/s" : ` ${tile.unit}`}` : "";
  }
}
