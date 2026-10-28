// Network: requests made with `pn.fetch`, merged from their `start` and
// `end` / `error` records, with headers and body previews.

import { Panel, searchBox } from "./panel.js";
import { clock, copyButton, formatBytes, formatMs, h, icon } from "../util.js";

const MAX_REQUESTS = 500;

/** Fold one `network` event into the request map; returns the record. */
export function mergeRecord(records, target, data) {
  const key = `${target}:${data.id}`;
  let record = records.get(key);
  if (!record) {
    record = { key, target, id: data.id, state: "pending" };
    records.set(key, record);
  }
  if (data.phase === "start") {
    Object.assign(record, {
      method: data.method,
      url: data.url,
      request_headers: data.request_headers,
      request_body: data.request_body,
      request_size: data.request_size,
      started: data.started,
    });
  } else if (data.phase === "end") {
    Object.assign(record, {
      state: "done",
      status: data.status,
      final_url: data.url,
      response_headers: data.response_headers,
      response_body: data.response_body,
      response_size: data.response_size,
      duration_ms: data.duration_ms,
    });
  } else if (data.phase === "error") {
    Object.assign(record, { state: "error", error: data.error, duration_ms: data.duration_ms });
  }
  return record;
}

/** `{name, host}` for the table's Name column. */
export function splitUrl(url) {
  try {
    const parsed = new URL(String(url));
    const path = parsed.pathname.split("/").filter(Boolean);
    const name = (path[path.length - 1] || parsed.host) + parsed.search;
    return { name, host: parsed.host, path: parsed.pathname + parsed.search };
  } catch (err) {
    return { name: String(url || ""), host: "", path: String(url || "") };
  }
}

function headerPairs(headers) {
  if (!headers) return [];
  if (Array.isArray(headers)) return headers.map((pair) => [String(pair[0]), String(pair[1])]);
  return Object.entries(headers).map(([k, v]) => [k, String(v)]);
}

/** Pretty-print a body preview when it's JSON. */
export function prettyBody(text) {
  if (text == null) return "";
  const body = String(text);
  const trimmed = body.trim();
  if (!/^[[{]/.test(trimmed)) return body;
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch (err) {
    return body;
  }
}

export class NetworkPanel extends Panel {
  constructor(app) {
    super(app, "network", "Network");
    this.records = new Map();
    this.text = "";
    this.selected = null;
    this.detailTab = "headers";
    this.build();
  }

  build() {
    this.el.classList.add("network");
    this.search = searchBox("Filter URLs", (value) => {
      this.text = value.toLowerCase();
      this.render();
    });
    this.summary = h("span.toolbar-note");
    this.tbody = h("tbody");
    this.table = h(
      "table.grid",
      null,
      h(
        "thead",
        null,
        h(
          "tr",
          null,
          h("th.col-status", null, "Status"),
          h("th.col-method", null, "Method"),
          h("th.col-name", null, "Name"),
          h("th.col-target", null, "App"),
          h("th.col-size.num", null, "Size"),
          h("th.col-time.num", null, "Time"),
          h("th.col-start", null, "Started"),
        ),
      ),
      this.tbody,
    );
    this.tbody.addEventListener("click", (event) => {
      const row = event.target.closest("tr[data-key]");
      if (row) this.select(row.dataset.key);
    });
    this.tableWrap = h("div.grid-wrap", { tabIndex: 0 }, this.table);
    this.tableWrap.addEventListener("keydown", (event) => this.onKey(event));
    this.detail = h("div.pane.detail-pane");
    this.el.append(
      h(
        "div.toolbar",
        null,
        h("button.btn.btn-icon", { type: "button", title: "Clear requests", onclick: () => this.clear() }, icon("clear", 14)),
        h("span.toolbar-sep"),
        this.search,
        h("span.spacer"),
        this.summary,
      ),
      h("div.split.network-split", null, h("div.pane.grid-pane", null, this.tableWrap), this.detail),
    );
    this.render();
  }

  focusSearch() {
    this.search.focus();
    return true;
  }

  onHistoryStart() {
    this.records = new Map();
    this.replaying = true;
  }

  onHistoryEnd() {
    this.replaying = false;
    this.render();
  }

  onEvent(event, replay) {
    if (event.topic !== "network" || !event.data) return;
    const record = mergeRecord(this.records, event.target, event.data);
    while (this.records.size > MAX_REQUESTS) this.records.delete(this.records.keys().next().value);
    if (replay || this.replaying) return;
    const row = this.tbody.querySelector(`tr[data-key="${CSS.escape(record.key)}"]`);
    if (row) row.replaceWith(this.rowElement(record));
    else if (this.matches(record)) {
      this.tableWrap.querySelector(".empty")?.remove();
      this.tbody.appendChild(this.rowElement(record));
    }
    if (record.key === this.selected) this.renderDetail();
    this.renderSummary();
  }

  clear() {
    this.records = new Map();
    this.selected = null;
    this.app.conn.send({ type: "clear", target: null, topic: "network" });
    this.render();
  }

  matches(record) {
    if (!this.text) return true;
    return `${record.method || ""} ${record.url || ""} ${record.status || ""}`.toLowerCase().includes(this.text);
  }

  render() {
    this.tbody.textContent = "";
    this.tableWrap.querySelector(".empty")?.remove();
    const shown = [...this.records.values()].filter((r) => this.matches(r));
    for (const record of shown) this.tbody.appendChild(this.rowElement(record));
    if (!shown.length) {
      this.tableWrap.appendChild(
        this.records.size
          ? Panel.empty("Nothing matches the filter")
          : Panel.empty("No requests yet", "Requests made with pn.fetch in any app appear here."),
      );
    }
    this.renderSummary();
    this.renderDetail();
  }

  renderSummary() {
    const all = [...this.records.values()];
    const bytes = all.reduce((sum, r) => sum + (Number(r.response_size) || 0), 0);
    this.summary.textContent = all.length ? `${all.length} request${all.length === 1 ? "" : "s"} · ${formatBytes(bytes)} received` : "";
  }

  rowElement(record) {
    const { name, host } = splitUrl(record.url);
    const failed = record.state === "error" || Number(record.status) >= 400;
    const status =
      record.state === "pending" ? h("span.muted", null, "pending") : record.state === "error" ? h("span", { title: record.error }, "failed") : String(record.status ?? "");
    const row = h(
      `tr${failed ? ".failed" : ""}${record.state === "pending" ? ".pending" : ""}`,
      { dataset: { key: record.key }, "aria-selected": String(record.key === this.selected) },
      h("td.col-status", null, status),
      h("td.col-method", null, record.method || ""),
      h("td.col-name", { title: record.url || "" }, h("span.req-name", null, name), host ? h("span.req-host", null, host) : null),
      h("td.col-target", null, this.app.targetLabel(record.target)),
      h("td.col-size.num", null, record.state === "done" ? formatBytes(record.response_size) : ""),
      h("td.col-time.num", null, record.duration_ms != null ? formatMs(record.duration_ms) : ""),
      h("td.col-start", null, clock(record.started)),
    );
    if (record.key === this.selected) row.classList.add("selected");
    return row;
  }

  select(key) {
    this.selected = key;
    for (const row of this.tbody.querySelectorAll("tr.selected")) row.classList.remove("selected");
    const row = this.tbody.querySelector(`tr[data-key="${CSS.escape(key)}"]`);
    row?.classList.add("selected");
    row?.scrollIntoView({ block: "nearest" });
    this.renderDetail();
  }

  onKey(event) {
    const rows = [...this.tbody.querySelectorAll("tr[data-key]")];
    if (!rows.length) return;
    const index = rows.findIndex((row) => row.dataset.key === this.selected);
    let next = null;
    if (event.key === "ArrowDown") next = rows[Math.min(rows.length - 1, index + 1)];
    else if (event.key === "ArrowUp") next = rows[Math.max(0, index - 1)];
    else if (event.key === "Escape") {
      this.selected = null;
      this.render();
      return;
    } else return;
    event.preventDefault();
    if (next) this.select(next.dataset.key);
  }

  renderDetail() {
    const box = this.detail;
    box.textContent = "";
    const record = this.selected ? this.records.get(this.selected) : null;
    box.classList.toggle("hidden-pane", !record);
    this.el.classList.toggle("has-detail", !!record);
    if (!record) return;
    const tabs = h("div.subtabs", { role: "tablist" });
    for (const [id, label] of [["headers", "Headers"], ["request", "Request"], ["response", "Response"]]) {
      tabs.appendChild(
        h(
          `button.subtab${this.detailTab === id ? ".active" : ""}`,
          {
            type: "button",
            role: "tab",
            "aria-selected": String(this.detailTab === id),
            onclick: () => {
              this.detailTab = id;
              this.renderDetail();
            },
          },
          label,
        ),
      );
    }
    tabs.appendChild(h("span.spacer"));
    tabs.appendChild(
      h("button.btn.btn-icon", { type: "button", title: "Close", "aria-label": "Close details", onclick: () => this.select(null) }, "✕"),
    );
    box.appendChild(tabs);
    const body = h("div.detail-body");
    if (this.detailTab === "headers") {
      const general = [
        ["URL", record.url || ""],
        ["Method", record.method || ""],
        ["Status", record.state === "error" ? `failed: ${record.error}` : record.state === "pending" ? "pending" : String(record.status ?? "")],
        ["App", this.app.targetLabel(record.target)],
        ["Started", clock(record.started, { millis: true })],
        ["Duration", record.duration_ms != null ? formatMs(record.duration_ms) : ""],
        ["Sent", formatBytes(record.request_size)],
        ["Received", record.state === "done" ? formatBytes(record.response_size) : ""],
      ];
      if (record.final_url && record.final_url !== record.url) general.splice(1, 0, ["Final URL", record.final_url]);
      body.append(
        this.kvSection("General", general),
        this.kvSection("Response headers", headerPairs(record.response_headers)),
        this.kvSection("Request headers", headerPairs(record.request_headers)),
      );
    } else {
      const text = this.detailTab === "request" ? record.request_body : record.response_body;
      if (text == null || text === "") body.appendChild(Panel.empty(this.detailTab === "request" ? "No request body" : record.state === "pending" ? "Waiting for the response..." : "No response body"));
      else {
        const pretty = prettyBody(text);
        body.append(h("div.body-actions", null, copyButton(pretty)), h("pre.body-preview", null, pretty));
      }
    }
    box.appendChild(body);
  }

  kvSection(title, pairs) {
    const table = h("table.kv");
    for (const [key, value] of pairs) table.appendChild(h("tr", null, h("th", null, key), h("td", null, value)));
    return h("details.section", { open: true }, h("summary.section-title", null, title), pairs.length ? table : h("div.none", null, "None"));
  }
}
