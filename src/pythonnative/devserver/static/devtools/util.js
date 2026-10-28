// Small DOM and formatting helpers shared by the DevTools panels.

/**
 * Create an element: `h("button.primary", {title: "Go", onclick}, "Go")`.
 * The selector takes a tag plus `.class` and `#id` parts; attributes
 * starting with `on` become listeners, `dataset` and `style` objects are
 * merged, `false` and `null` attributes are skipped, and children may be
 * strings, nodes, arrays, or falsy (skipped).
 */
export function h(selector, attrs = null, ...children) {
  const match = /^([a-z0-9-]+)?((?:[.#][\w-]+)*)$/i.exec(selector);
  const node = document.createElement(match?.[1] || "div");
  for (const part of (match?.[2] || "").match(/[.#][\w-]+/g) || []) {
    if (part[0] === ".") node.classList.add(part.slice(1));
    else node.id = part.slice(1);
  }
  if (attrs && (typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs))) {
    children.unshift(attrs);
    attrs = null;
  }
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === false || value == null) continue;
    if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key === "className") node.className = value;
    else if (key in node && typeof value !== "string") node[key] = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children) {
    if (child == null || child === false || child === "") continue;
    if (Array.isArray(child)) append(node, child);
    else node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** An inline SVG icon from a path list (24x24 viewBox, stroked). */
export function icon(name, size = 14) {
  const paths = ICONS[name] || "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("icon");
  svg.innerHTML = paths;
  return svg;
}

const ICONS = {
  reload: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  menu: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  bug: '<path d="M8 8a4 4 0 0 1 8 0v1H8z"/><rect x="7" y="9" width="10" height="11" rx="5"/><path d="M12 13v7M3 13h4M17 13h4M4 7l3 2M20 7l-3 2M4 20l3-2M20 20l-3-2"/>',
  inspect: '<path d="M3 3l7 17 2.5-7.5L20 10z"/><path d="M13 13l6 6"/>',
  clear: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  open: '<path d="M14 3h7v7"/><path d="M10 14L21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>',
  record: '<circle cx="12" cy="12" r="6" fill="currentColor"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  down: '<path d="M12 5v14M5 12l7 7 7-7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
};

/** Persisted preferences (localStorage; every access may throw). */
export const prefs = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(`pn-devtools:${key}`);
      return raw == null ? fallback : JSON.parse(raw);
    } catch (err) {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`pn-devtools:${key}`, JSON.stringify(value));
    } catch (err) {
      /* storage blocked or full; preferences are a convenience */
    }
  },
};

export function debounce(fn, ms) {
  let timer = 0;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

/** `09:41:07.123` for a Unix time in seconds. */
export function clock(seconds, { millis = false } = {}) {
  if (!seconds) return "";
  const date = new Date(seconds * 1000);
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  const base = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  return millis ? `${base}.${pad(date.getMilliseconds(), 3)}` : base;
}

export function formatBytes(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return n === 0 ? "0 B" : "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatMs(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n)) return "";
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 2)} s`;
  if (n >= 100) return `${Math.round(n)} ms`;
  return `${n.toFixed(n >= 10 ? 1 : 2).replace(/\.?0+$/, "") || "0"} ms`;
}

/** Copy text; resolves to whether it worked. */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(String(text));
    return true;
  } catch (err) {
    const area = h("textarea", { style: { position: "fixed", opacity: "0" } }, String(text));
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e) {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

/** A button that copies `text()` and briefly confirms. */
export function copyButton(text, label = "Copy") {
  const button = h("button.btn.btn-small", { type: "button", title: "Copy to the clipboard" }, icon("copy", 12), h("span", null, label));
  button.addEventListener("click", async () => {
    const ok = await copyText(typeof text === "function" ? text() : text);
    const span = button.querySelector("span");
    span.textContent = ok ? "Copied" : "Couldn't copy";
    setTimeout(() => (span.textContent = label), 1400);
  });
  return button;
}

/** Download a JSON document as a file. */
export function downloadJSON(name, document_) {
  const blob = new Blob([JSON.stringify(document_)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** Whether keyboard focus is in a text field (so global shortcuts stay out of the way). */
export function typing(event) {
  const t = event.target;
  return !!t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
}

/** Badge text and class for a target kind. */
export function kindBadge(kind) {
  if (kind === "go") return { text: "Go", cls: "badge-go" };
  if (kind === "preview") return { text: "Preview", cls: "badge-preview" };
  return { text: "App", cls: "badge-app" };
}
