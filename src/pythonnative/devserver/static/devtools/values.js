// Render the agent's value summaries (`pythonnative.devtools.inspector.summarize`):
// `{type, repr, literal?, source?, items?: [[key, summary]], more?}`.

import { h } from "./util.js";

/** CSS class for a summary's value text, by Python type. */
export function valueClass(summary) {
  const type = summary?.type;
  if (type === "str") return "v-str";
  if (type === "int" || type === "float" || type === "complex") return "v-num";
  if (type === "bool" || type === "NoneType") return "v-const";
  if (type === "function") return "v-fn";
  if (type === "Element") return "v-element";
  if (summary?.items) return "v-container";
  return "v-obj";
}

/** The value text: the repr, or a placeholder for a missing summary. */
export function valueText(summary) {
  if (!summary || typeof summary !== "object") return "undefined";
  return summary.repr == null ? `<${summary.type || "?"}>` : String(summary.repr);
}

/**
 * One expandable property row: `name: value  type`.
 *
 * @param name The key (string), or null for a bare value.
 * @param summary The value summary.
 * @param options.depth Indentation depth (for nested items).
 * @param options.valueNode Replace the value text (e.g. an editor).
 * @param options.prefix Element shown before the name (a hook's position).
 */
export function valueRow(name, summary, { depth = 0, valueNode = null, prefix = null, expanded = false } = {}) {
  const items = Array.isArray(summary?.items) ? summary.items : null;
  const wrap = h("div.value", { role: items ? "treeitem" : null });
  const twisty = h("span.twisty", { "aria-hidden": "true" });
  const row = h(
    "div.value-row",
    { style: { paddingLeft: `${depth * 14 + 4}px` } },
    twisty,
    prefix,
    name != null ? h("span.value-key", null, String(name)) : null,
    name != null ? h("span.value-colon", null, ":") : null,
    valueNode || h(`span.value-text.${valueClass(summary)}`, { title: valueText(summary) }, valueText(summary)),
    summary?.type && !valueNode ? h("span.value-type", null, summary.type) : null,
  );
  wrap.appendChild(row);
  if (!items || !items.length) return wrap;

  twisty.classList.add("has-children");
  row.classList.add("expandable");
  row.tabIndex = 0;
  let body = null;
  const toggle = (open) => {
    const next = open ?? !wrap.classList.contains("open");
    wrap.classList.toggle("open", next);
    wrap.setAttribute("aria-expanded", String(next));
    if (next && !body) {
      body = h("div.value-children");
      for (const [key, child] of items) body.appendChild(valueRow(key, child, { depth: depth + 1 }));
      if (summary.more) body.appendChild(h("div.value-row.value-more", { style: { paddingLeft: `${(depth + 1) * 14 + 18}px` } }, "…more items not shown"));
      wrap.appendChild(body);
    }
    if (body) body.hidden = !next;
  };
  row.addEventListener("click", (event) => {
    if (event.target.closest("input, button")) return;
    toggle();
  });
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") toggle();
    else if (event.key === "ArrowRight") toggle(true);
    else if (event.key === "ArrowLeft") toggle(false);
    else return;
    event.preventDefault();
  });
  toggle(expanded);
  return wrap;
}
