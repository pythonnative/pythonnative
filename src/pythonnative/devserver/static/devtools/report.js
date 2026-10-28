// Render an error report (`pythonnative.errors.ErrorReport.to_dict()`)
// as DOM. The browser preview's error overlay and the DevTools Problems
// panel share this; each page styles the `pn-report-*` classes itself.
//
// Report keys: level, phase, type, message, title, component_stack
// ([{name, file, line}], innermost first), frames ([{file, line,
// function, code, title, excerpt, framework}], innermost last, like a
// traceback), text (the formatted traceback), timestamp.

/**
 * `"render error"`, `"warning"`: a short label for the report's phase.
 */
export function phaseLabel(report) {
  if (!report) return "";
  if (report.level === "warning") return "Warning";
  const phase = String(report.phase || "runtime");
  return `${phase.charAt(0).toUpperCase()}${phase.slice(1)} error`;
}

/**
 * Group frames for display, innermost first: application frames stand
 * alone and runs of framework frames collapse into one group.
 *
 * @returns {Array<{framework: false, frame} | {framework: true, frames}>}
 */
export function groupFrames(frames) {
  const groups = [];
  const ordered = Array.isArray(frames) ? [...frames].reverse() : [];
  for (const frame of ordered) {
    if (!frame) continue;
    const last = groups[groups.length - 1];
    if (frame.framework) {
      if (last && last.framework) last.frames.push(frame);
      else groups.push({ framework: true, frames: [frame] });
    } else {
      groups.push({ framework: false, frame });
    }
  }
  return groups;
}

/** `app/main.py:14` for a frame or component frame, or `""` without a file. */
export function location(entry) {
  if (!entry || !entry.file) return "";
  return entry.line ? `${entry.file}:${entry.line}` : String(entry.file);
}

/**
 * Build the report's body: message, component stack, and call stack.
 *
 * @param report The report dict.
 * @param options.onOpen `(file, line) => void`; frame titles and component
 *   locations become buttons that call it. Without it they're plain text.
 * @param options.showFramework Expand framework frame groups initially.
 * @param options.message Include the message paragraph (default true).
 */
export function renderReport(report, { onOpen = null, showFramework = false, message = true } = {}) {
  const root = el("div", "pn-report");
  root.classList.add(report?.level === "warning" ? "pn-report-warning" : "pn-report-error");
  if (message && report?.message) root.appendChild(el("p", "pn-report-message", String(report.message)));

  const components = Array.isArray(report?.component_stack) ? report.component_stack : [];
  if (components.length) {
    const section = el("section", "pn-report-section pn-report-components");
    section.appendChild(el("h3", "pn-report-heading", "Component stack"));
    const list = el("ol", "pn-report-component-list");
    for (const component of components) {
      const item = el("li", "pn-report-component");
      item.appendChild(el("span", "pn-report-component-name", `<${component?.name || "?"}>`));
      const where = location(component);
      if (where) item.appendChild(link(where, component, onOpen, "pn-report-location"));
      list.appendChild(item);
    }
    section.appendChild(list);
    root.appendChild(section);
  }

  const groups = groupFrames(report?.frames);
  if (groups.length) {
    const section = el("section", "pn-report-section pn-report-frames");
    section.appendChild(el("h3", "pn-report-heading", "Call stack"));
    for (const group of groups) {
      if (!group.framework) {
        section.appendChild(renderFrame(group.frame, onOpen, true));
        continue;
      }
      const details = el("details", "pn-report-framework");
      details.open = !!showFramework;
      const count = group.frames.length;
      details.appendChild(el("summary", "pn-report-framework-summary", `${count} framework frame${count === 1 ? "" : "s"}`));
      for (const frame of group.frames) details.appendChild(renderFrame(frame, onOpen, false));
      section.appendChild(details);
    }
    root.appendChild(section);
  }
  return root;
}

function renderFrame(frame, onOpen, withExcerpt) {
  const row = el("div", frame.framework ? "pn-report-frame pn-report-frame-framework" : "pn-report-frame");
  const title = frame.title || `${location(frame)} in ${frame.function || "?"}`;
  row.appendChild(link(title, frame, onOpen, "pn-report-frame-title"));
  const excerpt = typeof frame.excerpt === "string" ? frame.excerpt : "";
  if (withExcerpt && excerpt) {
    const pre = el("pre", "pn-report-excerpt");
    for (const line of excerpt.split("\n")) {
      const current = line.startsWith(">");
      pre.appendChild(el("span", current ? "pn-report-line pn-report-line-current" : "pn-report-line", line));
    }
    row.appendChild(pre);
  } else if (!withExcerpt && frame.code) {
    row.appendChild(el("code", "pn-report-code", String(frame.code)));
  }
  return row;
}

function link(text, entry, onOpen, className) {
  if (typeof onOpen !== "function" || !entry?.file) return el("span", className, text);
  const button = el("button", `${className} pn-report-link`, text);
  button.type = "button";
  button.title = `Open ${location(entry)} in your editor`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onOpen(String(entry.file), Number(entry.line) || 1);
  });
  return button;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}
