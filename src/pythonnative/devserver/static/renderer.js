// The DOM mounting layer for the browser preview.
//
// This module plays the role `PNMounter` (Swift) and `Mounter` (Kotlin)
// play on device. The renderer core runs in the page as WebAssembly
// (`core/mount.js`): it validates each commit, lays it out with Yoga,
// flattens layout-only views, and hands this renderer decoded mount
// transactions (create, update, insert, delete, frame, and command ops),
// which it applies through the component managers. The renderer measures
// text and intrinsic leaves for the core, reports container and image
// sizes back to it, forwards input to it (`pn_core_event` and
// `pn_core_pointer`), and applies its animated writes. Frames use points,
// represented by CSS pixels inside the phone frame.
//
// Component managers mirror the Swift `PN*Manager` classes prop for
// prop (see docs/concepts/bridge.md and the iOS sources).

import { color as parseColor, isColorProp } from "./colors.js";
import { assets } from "./assets.js";
import { POINTER_CANCEL, POINTER_DOWN, POINTER_MOVE, POINTER_UP } from "./core/mount.js";

/** Height of a native-stack navigation bar, and of one with a large title. */
export const STACK_HEADER = 44;
export const STACK_LARGE_HEADER = 96;

/**
 * Height of the navigation bar a native-stack `Screen` reserves above its
 * content, read from the same options the iOS and Android stacks read.
 */
export function stackHeaderHeight(props) {
  if (!props || props.header_shown === false) return 0;
  return props.header_large_title ? STACK_LARGE_HEADER : STACK_HEADER;
}

const INF = 1e6;
const isFiniteConstraint = (v) => typeof v === "number" && v > 0 && v < INF / 2;
const px = (v) => `${Math.round(v * 100) / 100}px`;

// ---------------------------------------------------------------------------
// Shared style application
// ---------------------------------------------------------------------------

const FONT_WEIGHTS = {
  ultralight: 100,
  thin: 200,
  light: 300,
  regular: 400,
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  heavy: 800,
  black: 900,
};

const COMMON_KEYS = new Set([
  "background_color",
  "overflow",
  "display",
  "opacity",
  "z_index",
  "pointer_events",
  "hit_slop",
  "border_radius",
  "border_top_left_radius",
  "border_top_right_radius",
  "border_bottom_left_radius",
  "border_bottom_right_radius",
  "border_width",
  "border_color",
  "border_left_width",
  "border_top_width",
  "border_right_width",
  "border_bottom_width",
  "border_left_color",
  "border_top_color",
  "border_right_color",
  "border_bottom_color",
  "shadow_color",
  "shadow_opacity",
  "shadow_radius",
  "shadow_offset",
  "elevation",
  "transform",
  "border_style",
  "accessible",
  "accessibility_label",
  "accessibility_hint",
  "accessibility_role",
  "accessibility_state",
  "accessibility_live_region",
  "accessibility_value",
  "accessibility_actions",
  "important_for_accessibility",
  "test_id",
]);

function offsetOf(value) {
  if (Array.isArray(value)) return { x: Number(value[0]) || 0, y: Number(value[1]) || 0 };
  if (value && typeof value === "object") return { x: Number(value.width) || 0, y: Number(value.height) || 0 };
  return { x: 0, y: 0 };
}

/** Degrees or radians, as the wire spells them (`"45deg"`, `"0.5rad"`, or a bare number of degrees). */
function angle(raw, n) {
  return typeof raw === "string" && raw.endsWith("rad") ? `${n}rad` : `${n}deg`;
}

/**
 * The transform operations every renderer supports (RFC 0002): `rotate`,
 * `rotate_x`, `rotate_y`, `rotate_z`, `scale`, `scale_x`, `scale_y`,
 * `translate_x`, `translate_y`, `skew_x`, `skew_y`, and `perspective`.
 * `perspective` is hoisted to the front, as CSS requires.
 */
export function transformToCSS(value) {
  if (value == null) return "";
  const ops = Array.isArray(value) ? value : [value];
  const parts = [];
  let perspective = "";
  for (const op of ops) {
    if (!op || typeof op !== "object") continue;
    for (const [key, raw] of Object.entries(op)) {
      const n = typeof raw === "string" ? parseFloat(raw) : Number(raw);
      if (!Number.isFinite(n)) return "";
      switch (key) {
        case "rotate":
        case "rotate_z":
          parts.push(`rotate${key === "rotate_z" ? "Z" : ""}(${angle(raw, n)})`);
          break;
        case "rotate_x":
          parts.push(`rotateX(${angle(raw, n)})`);
          break;
        case "rotate_y":
          parts.push(`rotateY(${angle(raw, n)})`);
          break;
        case "scale":
          parts.push(`scale(${n})`);
          break;
        case "scale_x":
          parts.push(`scaleX(${n})`);
          break;
        case "scale_y":
          parts.push(`scaleY(${n})`);
          break;
        case "translate_x":
          parts.push(`translateX(${n}px)`);
          break;
        case "translate_y":
          parts.push(`translateY(${n}px)`);
          break;
        case "skew_x":
          parts.push(`skewX(${angle(raw, n)})`);
          break;
        case "skew_y":
          parts.push(`skewY(${angle(raw, n)})`);
          break;
        case "perspective":
          if (n > 0) perspective = `perspective(${n}px)`;
          break;
        default:
          break;
      }
    }
  }
  return [perspective, ...parts].filter(Boolean).join(" ");
}

const LIVE_REGIONS = { polite: "polite", assertive: "assertive", none: "off" };
const BORDER_STYLES = new Set(["solid", "dashed", "dotted"]);

/**
 * Style keys shared by containers and leaves. `leaf` skips the
 * container-only ones; `background: false` leaves `background_color` to a
 * manager that paints its own (a switch track, a progress track).
 */
export function applyStyle(view, props, changed, scheme, { leaf = false, background = true } = {}) {
  const el = view.el;
  const s = el.style;
  const c = (v) => parseColor(v, scheme);
  const has = (k) => k in changed;

  if (background && has("background_color")) s.backgroundColor = c(props.background_color) ?? "";
  if (has("display")) s.display = props.display === "none" ? "none" : "";
  if (has("z_index")) s.zIndex = props.z_index == null ? "" : String(props.z_index);
  if (!leaf) {
    if (has("overflow")) s.overflow = props.overflow === "hidden" ? "hidden" : "";
    if (has("pointer_events")) {
      const mode = props.pointer_events;
      view.pointerMode = mode;
      s.pointerEvents = mode === "none" || mode === "box_none" ? "none" : "";
      for (const child of view.children) applyPointerInheritance(child, view);
    }
  }
  if (has("opacity")) {
    view.baseOpacity = props.opacity == null ? 1 : Number(props.opacity);
    if (!view.pressedOpacityActive) s.opacity = props.opacity == null ? "" : String(props.opacity);
  }

  // Corners.
  const cornerKeys = [
    "border_radius",
    "border_top_left_radius",
    "border_top_right_radius",
    "border_bottom_left_radius",
    "border_bottom_right_radius",
  ];
  if (cornerKeys.some(has)) {
    const r = props.border_radius;
    const tl = props.border_top_left_radius ?? r;
    const tr = props.border_top_right_radius ?? r;
    const br = props.border_bottom_right_radius ?? r;
    const bl = props.border_bottom_left_radius ?? r;
    if ([tl, tr, br, bl].every((v) => v == null)) {
      s.borderRadius = "";
    } else {
      s.borderRadius = [tl, tr, br, bl].map((v) => px(Number(v) || 0)).join(" ");
    }
    // iOS masks to bounds when a radius is set (unless a shadow asks otherwise).
    if (r != null && !leaf && !view.hasShadow) s.overflow = props.overflow === "hidden" || r ? "hidden" : "";
  }

  // Borders: uniform or per side.
  const borderKeys = [
    "border_width",
    "border_color",
    "border_style",
    "border_left_width",
    "border_top_width",
    "border_right_width",
    "border_bottom_width",
    "border_left_color",
    "border_top_color",
    "border_right_color",
    "border_bottom_color",
  ];
  if (borderKeys.some(has)) {
    const uniformColor = c(props.border_color) ?? "#000";
    const uniform = Number(props.border_width) || 0;
    const style = BORDER_STYLES.has(props.border_style) ? props.border_style : "solid";
    const sides = ["top", "right", "bottom", "left"];
    for (const side of sides) {
      const width = props[`border_${side}_width`];
      const sideColor = c(props[`border_${side}_color`]);
      const w = width != null ? Number(width) || 0 : uniform;
      const Side = side[0].toUpperCase() + side.slice(1);
      s[`border${Side}`] = w > 0 ? `${px(w)} ${style} ${sideColor ?? uniformColor}` : "";
    }
  }

  // Shadows.
  const shadowKeys = ["shadow_color", "shadow_opacity", "shadow_radius", "shadow_offset", "elevation"];
  if (shadowKeys.some(has)) {
    const anyShadow = shadowKeys.some((k) => props[k] != null);
    view.hasShadow = anyShadow;
    if (!anyShadow) {
      s.boxShadow = "";
    } else {
      const off = offsetOf(props.shadow_offset);
      const radius = props.shadow_radius != null ? Number(props.shadow_radius) : Number(props.elevation) || 3;
      const opacity = props.shadow_opacity != null ? Number(props.shadow_opacity) : props.elevation != null ? 0.25 : 0;
      const base = c(props.shadow_color) ?? "#000";
      const elevY = props.elevation != null && props.shadow_offset == null ? Number(props.elevation) / 2 : off.y;
      s.boxShadow = `${px(off.x)} ${px(elevY)} ${px(radius * 2)} ${withAlpha(base, opacity)}`;
      if (!leaf && props.overflow !== "hidden") s.overflow = "";
    }
  }

  if (has("transform")) {
    view.staticTransform = transformToCSS(props.transform);
    composeTransform(view);
  }

  // Accessibility.
  if (has("accessibility_label")) {
    if (props.accessibility_label) el.setAttribute("aria-label", String(props.accessibility_label));
    else el.removeAttribute("aria-label");
  }
  if (has("accessibility_hint")) {
    if (props.accessibility_hint) el.setAttribute("title", String(props.accessibility_hint));
    else el.removeAttribute("title");
  }
  if (has("accessibility_role")) {
    if (props.accessibility_role) el.setAttribute("role", String(props.accessibility_role));
    else el.removeAttribute("role");
  }
  if (has("test_id")) {
    if (props.test_id) el.dataset.testid = String(props.test_id);
    else delete el.dataset.testid;
  }
  if (has("accessibility_state") && props.accessibility_state && typeof props.accessibility_state === "object") {
    const st = props.accessibility_state;
    if ("disabled" in st) el.setAttribute("aria-disabled", String(!!st.disabled));
    if ("selected" in st) el.setAttribute("aria-selected", String(!!st.selected));
    if ("checked" in st) el.setAttribute("aria-checked", String(st.checked));
  }
  if (has("accessibility_live_region")) {
    const live = LIVE_REGIONS[props.accessibility_live_region];
    if (live) {
      el.setAttribute("aria-live", live);
      el.setAttribute("aria-atomic", "true");
    } else {
      el.removeAttribute("aria-live");
      el.removeAttribute("aria-atomic");
    }
  }
  if (has("accessibility_value")) applyAccessibilityValue(el, props.accessibility_value);
  if (has("accessibility_actions")) applyAccessibilityActions(view, props.accessibility_actions);
  if (has("important_for_accessibility")) applyImportance(view, props.important_for_accessibility);
}

/** `accessibility_value` is a string (`aria-valuetext`) or `{min, max, now, text}` (the `aria-value*` set). */
function applyAccessibilityValue(el, value) {
  for (const name of ["aria-valuemin", "aria-valuemax", "aria-valuenow", "aria-valuetext"]) el.removeAttribute(name);
  if (value == null) return;
  if (typeof value !== "object") {
    el.setAttribute("aria-valuetext", String(value));
    return;
  }
  const pairs = [["min", "aria-valuemin"], ["max", "aria-valuemax"], ["now", "aria-valuenow"], ["text", "aria-valuetext"]];
  for (const [key, name] of pairs) if (value[key] != null) el.setAttribute(name, String(value[key]));
}

/**
 * The DOM has no custom accessibility actions. The names are exposed on
 * `data-pn-actions` for tooling, and the one action the keyboard can
 * trigger, `activate`, fires `on_accessibility_action("activate")` on
 * Enter or Space while the view is focused.
 */
function applyAccessibilityActions(view, actions) {
  const el = view.el;
  const names = Array.isArray(actions) ? actions.map((a) => (a && typeof a === "object" ? a.name : a)).filter((n) => n != null).map(String) : [];
  if (!names.length) {
    delete el.dataset.pnActions;
    if (view.a11yFocusable) {
      el.removeAttribute("tabindex");
      view.a11yFocusable = false;
    }
    return;
  }
  el.dataset.pnActions = JSON.stringify(names);
  if (!el.hasAttribute("tabindex") && view.importance !== "no") {
    el.tabIndex = 0;
    view.a11yFocusable = true;
  }
  if (!view.a11yKeyInstalled) {
    view.a11yKeyInstalled = true;
    el.addEventListener("keydown", (event) => {
      if (event.target !== el || (event.key !== "Enter" && event.key !== " ")) return;
      let current = [];
      try {
        current = JSON.parse(el.dataset.pnActions || "[]");
      } catch (err) {
        current = [];
      }
      if (!current.includes("activate")) return;
      event.preventDefault();
      view.ctx.emit(view.tag, "on_accessibility_action", ["activate"]);
    });
  }
}

/**
 * `important_for_accessibility`: `no_hide_descendants` hides the subtree
 * (`aria-hidden`); `no` drops the view's own semantics and focusability
 * (`role="presentation"`, `tabindex="-1"`) while its descendants stay
 * reachable, which is what React Native's `no` means; `yes` and `auto`
 * restore the defaults.
 */
function applyImportance(view, mode) {
  const el = view.el;
  const previous = view.importance;
  view.importance = mode;
  if (mode === "no_hide_descendants") {
    el.setAttribute("aria-hidden", "true");
  } else if (previous === "no_hide_descendants") {
    el.removeAttribute("aria-hidden");
  }
  if (mode === "no") {
    if (!view.props.accessibility_role) el.setAttribute("role", "presentation");
    el.tabIndex = -1;
  } else if (previous === "no") {
    if (el.getAttribute("role") === "presentation") el.removeAttribute("role");
    if (view.a11yFocusable || view.type === "Pressable") el.tabIndex = 0;
    else el.removeAttribute("tabindex");
  }
}

function applyPointerInheritance(child, parent) {
  const mode = parent.pointerMode;
  if (mode === "box_none") child.el.style.pointerEvents = child.pointerMode === "none" ? "none" : "auto";
  else if (mode === "box_only") child.el.style.pointerEvents = "none";
}

function withAlpha(cssColor, alpha) {
  const probe = document.createElement("span");
  probe.style.color = cssColor;
  document.body.appendChild(probe);
  const rgb = getComputedStyle(probe).color;
  probe.remove();
  const m = /rgba?\(([^)]+)\)/.exec(rgb);
  if (!m) return cssColor;
  const parts = m[1].split(",").map((p) => parseFloat(p));
  return `rgba(${parts[0]}, ${parts[1]}, ${parts[2]}, ${Math.max(0, Math.min(1, alpha))})`;
}

/** Combine the static `transform` prop with animated transform values (animation wins). */
export function composeTransform(view) {
  const anim = view.animTransform;
  let css = view.staticTransform || "";
  if (anim && Object.keys(anim).length) {
    const parts = [];
    if (anim.translate_x != null) parts.push(`translateX(${anim.translate_x}px)`);
    if (anim.translate_y != null) parts.push(`translateY(${anim.translate_y}px)`);
    if (anim.scale != null) parts.push(`scale(${anim.scale})`);
    if (anim.scale_x != null) parts.push(`scaleX(${anim.scale_x})`);
    if (anim.scale_y != null) parts.push(`scaleY(${anim.scale_y})`);
    if (anim.rotate != null) parts.push(`rotate(${anim.rotate}deg)`);
    if (anim.rotate_x != null) parts.push(`rotateX(${anim.rotate_x}deg)`);
    if (anim.rotate_y != null) parts.push(`rotateY(${anim.rotate_y}deg)`);
    css = parts.join(" ");
  }
  view.el.style.transform = css;
}

function applyTextStyle(el, props, changed, scheme) {
  const s = el.style;
  const has = (k) => k in changed;
  const c = (v) => parseColor(v, scheme);
  if (has("color")) s.color = c(props.color) ?? "";
  if (has("background_color")) s.backgroundColor = c(props.background_color) ?? "";
  if (has("font_size")) s.fontSize = props.font_size != null ? px(Number(props.font_size)) : "";
  if (has("font_weight") || has("bold")) {
    let weight = props.font_weight;
    if (typeof weight === "string") weight = FONT_WEIGHTS[weight.toLowerCase()] ?? weight;
    if (props.bold) weight = 700;
    s.fontWeight = weight == null ? "" : String(weight);
  }
  if (has("font_family")) s.fontFamily = props.font_family ? `"${props.font_family}", var(--pn-font)` : "";
  if (has("italic") || has("font_style")) s.fontStyle = props.italic || props.font_style === "italic" ? "italic" : "";
  if (has("text_align")) {
    const a = props.text_align;
    s.textAlign = a === "center" || a === "right" || a === "justify" ? a : a === "natural" ? "start" : "left";
  }
  if (has("letter_spacing")) s.letterSpacing = props.letter_spacing != null ? px(Number(props.letter_spacing)) : "";
  if (has("line_height")) s.lineHeight = props.line_height != null ? px(Number(props.line_height)) : "";
  if (has("text_decoration")) {
    const d = props.text_decoration;
    s.textDecoration = d === "underline" ? "underline" : d === "line_through" ? "line-through" : "";
  }
  if (has("text_transform")) {
    const t = props.text_transform;
    s.textTransform = t === "uppercase" || t === "lowercase" || t === "capitalize" ? t : "";
  }
  if (has("text_shadow_color") || has("text_shadow_offset") || has("text_shadow_radius")) {
    const col = c(props.text_shadow_color);
    if (!col) s.textShadow = "";
    else {
      const off = offsetOf(props.text_shadow_offset);
      s.textShadow = `${px(off.x)} ${px(off.y)} ${px(Number(props.text_shadow_radius) || 0)} ${col}`;
    }
  }
}

// ---------------------------------------------------------------------------
// Measurement
// ---------------------------------------------------------------------------

let measureRoot = null;

/** Natural size of `el` under the constraints, measured off-screen in unscaled px. */
export function measureElement(el, maxW, maxH, { block = false } = {}) {
  if (!measureRoot) measureRoot = document.getElementById("pn-measure") || document.body;
  const clone = el.cloneNode(true);
  clone.style.position = "static";
  clone.style.left = "auto";
  clone.style.top = "auto";
  clone.style.width = "auto";
  clone.style.height = "auto";
  clone.style.transform = "none";
  clone.style.display = block ? "block" : "inline-block";
  clone.style.maxWidth = isFiniteConstraint(maxW) ? px(maxW) : "none";
  clone.style.maxHeight = "none";
  clone.style.visibility = "hidden";
  measureRoot.appendChild(clone);
  const rect = clone.getBoundingClientRect();
  let width = Math.ceil(rect.width * 100) / 100;
  let height = Math.ceil(rect.height * 100) / 100;
  measureRoot.removeChild(clone);
  if (isFiniteConstraint(maxW)) width = Math.min(width, maxW);
  if (isFiniteConstraint(maxH)) height = Math.min(height, maxH);
  return [width, height];
}

// ---------------------------------------------------------------------------
// Component managers
// ---------------------------------------------------------------------------

class ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    applyStyle(view, view.props, changed, view.ctx.scheme());
  }
  container(view) {
    return view.el;
  }
  frame(view, x, y, w, h) {
    const s = view.el.style;
    s.left = px(x);
    s.top = px(y);
    s.width = px(w);
    s.height = px(h);
  }
  measure() {
    return [0, 0];
  }
  command() {
    return null;
  }
  destroy() {}
  childrenChanged() {}
}

class SpacerManager extends ViewManager {
  update() {}
}

const ELLIPSIS = "…";

class TextManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-text";
    view.el = el;
    view.maxLines = 0;
    view.truncated = null;
    // `on_press` on the label. Presses on a pressable span stop here so
    // the label doesn't also fire (`on_span_press` carries the index).
    el.addEventListener("click", (event) => {
      if (event.target.closest?.(".pn-span-pressable")) return;
      if (view.hasEvent("on_press")) view.ctx.emit(view.tag, "on_press", []);
    });
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    if ("text" in changed || "spans" in changed) this.render(view);
    applyTextStyle(el, props, changed, scheme);
    if ("max_lines" in changed || "ellipsize_mode" in changed) {
      const n = Number(props.max_lines) || 0;
      view.maxLines = n;
      view.ellipsize = props.ellipsize_mode || "tail";
      el.classList.toggle("pn-clamp", n > 1);
      el.classList.toggle("pn-clamp-1", n === 1);
      el.style.webkitLineClamp = n > 1 ? String(n) : "";
      // `tail` is the browser's own ellipsis; `clip` cuts without one.
      // `head` and `middle` have no CSS equivalent: a single clamped line
      // is truncated in JavaScript once its frame is known (see `frame`),
      // and multi-line `head`/`middle` render as `tail`.
      el.style.textOverflow = view.ellipsize === "clip" ? "clip" : "";
      if (view.truncated) this.render(view);
    }
    if ("selectable" in changed) el.classList.toggle("pn-selectable", !!props.selectable);
    // `allow_font_scaling` is Dynamic Type / Android `sp` opt-out; the
    // browser preview renders at font scale 1.0, so it has no effect.
    if ("on_press" in changed || "_pn_events" in changed) el.classList.toggle("pn-text-pressable", view.hasEvent("on_press"));
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
    if (view.frame && view.maxLines === 1 && (view.ellipsize === "head" || view.ellipsize === "middle")) this.truncate(view);
  }
  render(view) {
    const el = view.el;
    const props = view.props;
    el.textContent = "";
    view.truncated = null;
    if (Array.isArray(props.spans) && props.spans.length) {
      const scheme = view.ctx.scheme();
      props.spans.forEach((span, index) => {
        if (!span || typeof span !== "object") return;
        const node = document.createElement("span");
        node.textContent = span.text == null ? "" : String(span.text);
        applyTextStyle(node, span, span, scheme);
        if (span.pressable) {
          node.className = "pn-span-pressable";
          node.setAttribute("role", "link");
          node.tabIndex = 0;
          const press = (event) => {
            event.stopPropagation();
            view.ctx.emit(view.tag, "on_span_press", [index]);
          };
          node.addEventListener("click", press);
          node.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              press(event);
            }
          });
        }
        el.appendChild(node);
      });
      return;
    }
    el.textContent = props.text == null ? "" : String(props.text);
  }
  frame(view, x, y, w, h) {
    super.frame(view, x, y, w, h);
    if (view.maxLines === 1 && (view.ellipsize === "head" || view.ellipsize === "middle")) this.truncate(view);
  }
  /** JavaScript fallback for `head` / `middle` on one line of plain text (spans keep the browser's tail ellipsis). */
  truncate(view) {
    const el = view.el;
    const props = view.props;
    if (Array.isArray(props.spans) && props.spans.length) return;
    const full = props.text == null ? "" : String(props.text);
    if (view.truncated !== null) el.textContent = full;
    view.truncated = null;
    if (!el.isConnected || el.clientWidth <= 0 || el.scrollWidth <= el.clientWidth) return;
    const chars = [...full];
    const fits = (text) => {
      el.textContent = text;
      return el.scrollWidth <= el.clientWidth;
    };
    const candidate = (keep) => {
      if (view.ellipsize === "head") return ELLIPSIS + chars.slice(chars.length - keep).join("");
      const head = Math.ceil(keep / 2);
      return chars.slice(0, head).join("") + ELLIPSIS + chars.slice(chars.length - (keep - head)).join("");
    };
    let lo = 0;
    let hi = chars.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (fits(candidate(mid))) lo = mid;
      else hi = mid - 1;
    }
    view.truncated = candidate(lo);
    el.textContent = view.truncated;
  }
  measure(view, maxW, maxH) {
    const key = `${maxW}|${maxH}`;
    if (view.measureCache && view.measureCache.key === key) return view.measureCache.size;
    // Measure the full text, never the truncated copy.
    const truncated = view.truncated;
    if (truncated !== null) view.el.textContent = view.props.text == null ? "" : String(view.props.text);
    let size = measureElement(view.el, maxW, maxH, { block: true });
    if (truncated !== null) view.el.textContent = truncated;
    if (view.maxLines > 0) {
      const lh = parseFloat(getComputedStyle(view.el).lineHeight) || Number(view.props.font_size || 17) * 1.25;
      size = [size[0], Math.min(size[1], Math.ceil(lh * view.maxLines * 100) / 100)];
    }
    view.measureCache = { key, size };
    return size;
  }
  /** The first line's baseline at `width`: where a zero-height inline box sits on it. */
  baseline(view, width, height) {
    if (!measureRoot) measureRoot = document.getElementById("pn-measure") || document.body;
    const clone = view.el.cloneNode(true);
    Object.assign(clone.style, { position: "static", display: "block", width: width > 0 ? px(width) : "auto", height: "auto", transform: "none", visibility: "hidden" });
    const probe = document.createElement("span");
    probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
    clone.prepend(probe);
    measureRoot.appendChild(clone);
    const value = probe.getBoundingClientRect().bottom - clone.getBoundingClientRect().top;
    clone.remove();
    return Number.isFinite(value) && value > 0 ? Math.min(value, height) : height;
  }
}

class ButtonManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("button");
    el.className = "pn-view pn-button";
    el.type = "button";
    el.addEventListener("click", () => {
      if (!el.disabled) view.ctx.emit(view.tag, "on_press", []);
    });
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    if ("title" in changed) el.textContent = props.title == null ? "" : String(props.title);
    if ("font_size" in changed) el.style.fontSize = props.font_size != null ? px(Number(props.font_size)) : "";
    if ("color" in changed || "background_color" in changed) {
      const bg = parseColor(props.background_color, scheme);
      el.style.backgroundColor = bg ?? "";
      const color = parseColor(props.color, scheme);
      el.style.color = color ?? (bg ? "#fff" : "");
    }
    if ("disabled" in changed) el.disabled = props.disabled === true;
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
  }
  measure(view, maxW, maxH) {
    const [w, h] = measureElement(view.el, maxW, maxH);
    return [Math.max(44, Math.min(w + 24, isFiniteConstraint(maxW) ? maxW : Infinity)), Math.max(32, h + 12)];
  }
}

/**
 * `keyboard_type` -> `<input type>` and `inputmode`. The type carries the
 * browser's validation and native pickers where one exists; `inputmode`
 * picks the on-screen keyboard on touch devices, the closest the web gets
 * to iOS keyboard types.
 */
const KEYBOARD_TYPES = {
  default: { type: "text", inputmode: "" },
  ascii: { type: "text", inputmode: "text" },
  numbers_and_punctuation: { type: "text", inputmode: "decimal" },
  url: { type: "url", inputmode: "url" },
  number_pad: { type: "text", inputmode: "numeric" },
  numeric: { type: "text", inputmode: "numeric" },
  phone_pad: { type: "tel", inputmode: "tel" },
  email_address: { type: "email", inputmode: "email" },
  email: { type: "email", inputmode: "email" },
  decimal_pad: { type: "text", inputmode: "decimal" },
  decimal: { type: "text", inputmode: "decimal" },
  web_search: { type: "search", inputmode: "search" },
  visible_password: { type: "text", inputmode: "text" },
};

/** `on_key_press` reports the typed character, or `"Backspace"` / `"Enter"`, as React Native does. */
export function keyPressName(key) {
  if (key === "Backspace" || key === "Enter") return key;
  return typeof key === "string" && [...key].length === 1 ? key : null;
}

class TextInputManager extends ViewManager {
  create(view, props) {
    const multiline = !!props.multiline;
    const el = document.createElement(multiline ? "textarea" : "input");
    el.className = "pn-view pn-input";
    if (!multiline) el.type = "text";
    view.el = el;
    view.suppressEcho = false;
    view.composing = false;
    view.lastSelection = null;
    view.contentSize = null;
    el.addEventListener("compositionstart", () => { view.composing = true; });
    el.addEventListener("compositionend", () => {
      view.composing = false;
      if (view.pendingValue) { const pending = view.pendingValue; view.pendingValue = null; this.update(view, pending); }
    });
    el.addEventListener("input", () => {
      const props = view.props;
      if (props.max_length != null && el.value.length > Number(props.max_length)) {
        let limit = Number(props.max_length);
        const last = el.value.charCodeAt(limit - 1);
        if (last >= 0xD800 && last <= 0xDBFF) limit--;
        el.value = el.value.slice(0, limit);
      }
      view.ctx.emit(view.tag, "on_change", [el.value]);
      // A multiline input grows with its text: the core measures it again.
      view.ctx.invalidate?.(view.tag);
      this.reportContentSize(view);
    });
    // `select_text_on_focus`: select on focus, and keep the selection through
    // the `mouseup` of the click that focused the field (the browser would
    // otherwise collapse it to a caret).
    view.selectAllPending = false;
    el.addEventListener("focus", () => {
      view.ctx.emit(view.tag, "on_focus", []);
      if (view.props.select_text_on_focus && el.value) {
        el.select();
        view.selectAllPending = true;
      }
    });
    el.addEventListener("mouseup", (event) => {
      if (!view.selectAllPending) return;
      view.selectAllPending = false;
      event.preventDefault();
    });
    el.addEventListener("blur", () => {
      view.selectAllPending = false;
      view.ctx.emit(view.tag, "on_blur", []);
    });
    el.addEventListener("keydown", (event) => {
      const key = keyPressName(event.key);
      if (key && view.hasEvent("on_key_press")) view.ctx.emit(view.tag, "on_key_press", [{ key }]);
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      // Single-line inputs submit on Enter and blur unless told otherwise;
      // a multiline input keeps inserting newlines unless `blur_on_submit`
      // is set, in which case Enter submits and blurs instead.
      const blurOnSubmit = view.props.blur_on_submit != null ? !!view.props.blur_on_submit : !multiline;
      if (!multiline) {
        view.ctx.emit(view.tag, "on_submit", [el.value]);
        if (blurOnSubmit) el.blur();
      } else if (blurOnSubmit) {
        event.preventDefault();
        view.ctx.emit(view.tag, "on_submit", [el.value]);
        el.blur();
      }
    });
    view.selectionListener = () => {
      if (document.activeElement !== el) return;
      const selection = { start: el.selectionStart || 0, end: el.selectionEnd || 0 };
      view.lastSelection = selection;
      if (view.hasEvent("on_selection_change")) view.ctx.emit(view.tag, "on_selection_change", [selection]);
    };
    document.addEventListener("selectionchange", view.selectionListener);
    this.update(view, props);
    if (props.auto_focus) setTimeout(() => el.focus(), 0);
  }
  destroy(view) {
    document.removeEventListener("selectionchange", view.selectionListener);
  }
  frame(view, x, y, w, h) {
    super.frame(view, x, y, w, h);
    this.reportContentSize(view);
  }
  /** `on_content_size_change` for multiline inputs: the text's own extent, as `contentSize` on native. */
  reportContentSize(view) {
    const el = view.el;
    if (el.tagName !== "TEXTAREA" || !view.hasEvent("on_content_size_change") || !el.isConnected) return;
    const size = { width: el.clientWidth, height: el.scrollHeight };
    if (view.contentSize && view.contentSize.width === size.width && view.contentSize.height === size.height) return;
    view.contentSize = size;
    view.ctx.emit(view.tag, "on_content_size_change", [size]);
  }
  applyKeyboardType(view) {
    const el = view.el;
    const props = view.props;
    const spec = KEYBOARD_TYPES[props.keyboard_type] || KEYBOARD_TYPES.default;
    if (el.tagName === "INPUT") el.type = props.secure ? "password" : spec.type;
    if (spec.inputmode) el.inputMode = spec.inputmode;
    else el.removeAttribute("inputmode");
    // `visible_password` shows what would otherwise be dots; the browser
    // equivalent is a plain text field without password autofill.
    if (props.keyboard_type === "visible_password") el.autocomplete = "off";
  }
  /**
   * Controlled `selection` `{start, end}`. A value equal to the selection
   * the page itself just reported is Python echoing state back, so it is
   * left alone rather than yanking the caret from under the user.
   */
  applySelection(view, selection) {
    const el = view.el;
    if (!selection || typeof selection !== "object" || el.setSelectionRange == null) return;
    const length = el.value.length;
    const start = Math.max(0, Math.min(length, Number(selection.start) || 0));
    const end = Math.max(start, Math.min(length, selection.end != null ? Number(selection.end) : start));
    const last = view.lastSelection;
    if (last && last.start === start && last.end === end) return;
    if (el.selectionStart === start && el.selectionEnd === end) return;
    try {
      el.setSelectionRange(start, end);
    } catch (err) {
      /* not a text control (`type=email` etc. in some browsers) */
    }
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("value") && view.composing) view.pendingValue = {...changed};
    if (has("value") && props.value != null && !view.composing &&
        Number(changed._pn_edit_revision || 0) >= Number(view.editRevision || 0) && el.value !== String(props.value)) {
      const start = el.selectionStart, end = el.selectionEnd;
      el.value = String(props.value);
      if (start != null) el.setSelectionRange(Math.min(start, el.value.length), Math.min(end, el.value.length));
      this.reportContentSize(view);
    }
    if (has("selection")) this.applySelection(view, props.selection);
    if (has("placeholder")) el.placeholder = props.placeholder == null ? "" : String(props.placeholder);
    if (has("placeholder_color")) el.style.setProperty("--pn-placeholder", parseColor(props.placeholder_color, scheme) ?? "");
    if (has("font_size")) el.style.fontSize = props.font_size != null ? px(Number(props.font_size)) : "";
    if (has("color")) el.style.color = parseColor(props.color, scheme) ?? "";
    if (has("background_color")) el.style.backgroundColor = parseColor(props.background_color, scheme) ?? "";
    if (has("secure") || has("keyboard_type")) this.applyKeyboardType(view);
    // `keyboard_appearance` (light/dark keyboard) is an iOS keyboard skin; the browser has none.
    if (has("auto_capitalize")) el.autocapitalize = props.auto_capitalize || "sentences";
    if (has("auto_correct")) el.autocomplete = props.auto_correct === false ? "off" : "on";
    if (has("return_key_type")) el.enterKeyHint = props.return_key_type || "";
    if (has("selection_color")) el.style.caretColor = parseColor(props.selection_color, scheme) ?? "";
    if (has("editable")) el.readOnly = props.editable === false;
    if (has("max_length")) {
      if (props.max_length != null) el.maxLength = Number(props.max_length);
      else el.removeAttribute("maxlength");
    }
    if (has("text_content_type")) {
      const t = props.text_content_type;
      el.autocomplete =
        t === "password" ? "current-password" : t === "new_password" ? "new-password" : t === "one_time_code" ? "one-time-code" : t === "email" || t === "email_address" ? "email" : t === "username" ? "username" : t === "name" ? "name" : t === "telephone" || t === "phone" ? "tel" : t === "url" ? "url" : el.autocomplete;
    }
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  measure(view, maxW) {
    const width = isFiniteConstraint(maxW) ? Math.max(100, Math.min(maxW, 100)) : 100;
    if (view.el.tagName === "TEXTAREA") {
      // A textarea's own height follows its rows, not its text: lay a copy
      // out at the offered width and read the text's extent instead.
      if (!measureRoot) measureRoot = document.getElementById("pn-measure") || document.body;
      const box = document.createElement("div");
      box.style.cssText = `position:absolute;visibility:hidden;width:${isFiniteConstraint(maxW) ? px(maxW) : `${width}px`}`;
      const clone = view.el.cloneNode(true);
      clone.value = view.el.value;
      Object.assign(clone.style, { position: "static", display: "block", width: "100%", height: "0px", transform: "none" });
      box.appendChild(clone);
      measureRoot.appendChild(box);
      const h = Math.ceil(clone.scrollHeight + clone.offsetHeight - clone.clientHeight);
      box.remove();
      return [isFiniteConstraint(maxW) ? maxW : width, Math.max(36, h)];
    }
    return [isFiniteConstraint(maxW) ? Math.max(100, Math.min(maxW, 100)) : 100, 36];
  }
  command(view, name, args) {
    const el = view.el;
    switch (name) {
      case "focus":
        el.focus();
        return null;
      case "blur":
        el.blur();
        return null;
      case "clear":
        el.value = "";
        // `clear()` is an edit: report it so a controlled value follows.
        if (view.hasEvent("on_change")) view.ctx.emit(view.tag, "on_change", [""]);
        return null;
      case "get_value":
        return el.value;
      case "select_all":
        el.select(); return null;
      case "set_selection": {
        const start = Number(args.start) || 0;
        const end = args.end != null ? Number(args.end) : start;
        el.setSelectionRange(start, end);
        return null;
      }
      default:
        return null;
    }
  }
}

class ImageManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-image-wrap";
    const img = document.createElement("img");
    img.alt = "";
    img.draggable = false;
    const tint = document.createElement("div");
    tint.className = "pn-image-tint";
    tint.style.display = "none";
    el.appendChild(img);
    el.appendChild(tint);
    view.el = el;
    view.img = img;
    view.tint = tint;
    view.natural = null;
    view.assetScale = 1;
    view.loading = false;
    const loadEnd = () => {
      if (!view.loading) return;
      view.loading = false;
      if (view.hasEvent("on_load_end")) view.ctx.emit(view.tag, "on_load_end", []);
    };
    img.addEventListener("load", () => {
      const scale = view.assetScale || 1;
      view.natural = [img.naturalWidth / scale, img.naturalHeight / scale];
      view.measureCache = null;
      // `fade_duration`: the image fades in over the given milliseconds once decoded.
      const fade = Number(view.props.fade_duration);
      if (fade > 0 && img.style.opacity === "0") {
        img.style.transition = `opacity ${fade}ms ease-out`;
        requestAnimationFrame(() => { img.style.opacity = "1"; });
      } else {
        img.style.transition = "";
        img.style.opacity = "";
      }
      // The core sizes an image without an explicit size from what loaded.
      view.ctx.reportIntrinsic?.(view.tag, view.natural[0], view.natural[1]);
      view.ctx.emit(view.tag, "on_load", [{ width: view.natural[0], height: view.natural[1] }]);
      loadEnd();
    });
    img.addEventListener("error", () => {
      const fallback = imageSource(view.props.default_source);
      if (fallback && view.img.src !== new URL(fallback, location.href).href) {
        view.assetScale = assetScaleOf(view.props.default_source);
        view.img.src = fallback;
        return;
      }
      img.style.transition = "";
      img.style.opacity = "";
      view.ctx.emit(view.tag, "on_error", [`failed to load ${img.src}`]);
      loadEnd();
    });
    view.unsubscribeAssets = assets.onChange(() => {
      if (assets.isAssetUri(view.props.source) || assets.isAssetUri(view.props.default_source)) {
        this.update(view, { source: view.props.source });
      }
    });
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("source") || has("default_source")) {
      const src = imageSource(props.source);
      const fallback = imageSource(props.default_source);
      view.natural = null;
      // `headers` for network sources can't be attached to an `<img>`
      // request; the preview fetches the URL without them.
      if (src) {
        view.assetScale = assetScaleOf(props.source);
        view.loading = true;
        if (view.hasEvent("on_load_start")) view.ctx.emit(view.tag, "on_load_start", []);
        if (Number(props.fade_duration) > 0) {
          view.img.style.transition = "";
          view.img.style.opacity = "0";
        }
        // Show the local placeholder immediately for remote sources.
        if (fallback && /^https?:/.test(String(props.source))) view.img.src = fallback;
        view.img.src = src;
      } else if (fallback) {
        view.assetScale = assetScaleOf(props.default_source);
        view.img.src = fallback;
      } else {
        view.img.removeAttribute("src");
      }
      const maskSrc = src || fallback;
      view.tint.style.maskImage = view.tint.style.webkitMaskImage = maskSrc ? `url("${maskSrc}")` : "";
    }
    if (has("scale_type")) {
      const mode = props.scale_type;
      view.img.style.objectFit = mode === "cover" || mode === "repeat" ? "cover" : mode === "stretch" ? "fill" : mode === "center" ? "none" : "contain";
    }
    // An explicit `background_color` wins over the placeholder fill, as on iOS and Android.
    if (has("placeholder_color") || has("background_color")) {
      view.el.style.backgroundColor = parseColor(props.background_color ?? props.placeholder_color, scheme) ?? "";
    }
    if (has("tint_color")) {
      const tint = parseColor(props.tint_color, scheme);
      view.tint.style.display = tint ? "" : "none";
      view.tint.style.backgroundColor = tint ?? "";
      view.img.style.visibility = tint ? "hidden" : "";
    }
    if (has("blur_radius")) {
      const radius = Number(props.blur_radius) || 0;
      view.img.style.filter = radius > 0 ? `blur(${px(radius)})` : "";
      view.el.style.overflow = radius > 0 ? "hidden" : "";
    }
    applyStyle(view, props, changed, scheme, { leaf: true, background: false });
  }
  destroy(view) {
    if (view.unsubscribeAssets) view.unsubscribeAssets();
  }
}

function imageSource(source) {
  if (source == null) return "";
  if (typeof source === "object") source = source.uri ?? source.url ?? source.src ?? "";
  const text = String(source);
  if (!text) return "";
  if (assets.isAssetUri(text)) return assets.resolve(text) || "";
  if (/^(https?:|data:|blob:)/.test(text)) return text;
  if (text.startsWith("file://")) return `/file/${encodeURI(text.slice("file://".length).replace(/^\/+/, ""))}`;
  // An absolute path on the machine running the preview.
  return `/file/${encodeURI(text.replace(/^\/+/, ""))}`;
}

/** The density of the variant a bundled image resolves to (1 for anything else). */
function assetScaleOf(source) {
  const path = assets.pathOf(source);
  return path == null ? 1 : assets.scaleOf(path);
}

class SwitchManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-switch";
    el.setAttribute("role", "switch");
    const knob = document.createElement("div");
    knob.className = "pn-knob";
    el.appendChild(knob);
    el.addEventListener("click", () => {
      if (view.props.disabled === true) return;
      const next = !view.props.value;
      view.ctx.emit(view.tag, "on_change", [next]);
    });
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const el = view.el;
    if ("value" in changed || "on_tint_color" in changed || "tint_color" in changed) {
      const on = !!props.value;
      el.classList.toggle("pn-on", on);
      el.setAttribute("aria-checked", String(on));
      const onColor = parseColor(props.on_tint_color ?? props.tint_color, scheme) ?? "#34c759";
      el.style.backgroundColor = on ? onColor : "";
    }
    if ("thumb_color" in changed) el.firstChild.style.backgroundColor = parseColor(props.thumb_color, scheme) ?? "";
    if ("disabled" in changed) el.classList.toggle("pn-disabled", props.disabled === true);
    applyStyle(view, props, changed, scheme, { leaf: true, background: false });
  }
  /** UISwitch and the Material switch keep their intrinsic size at the frame's origin, however wide the frame. */
  frame(view, x, y, w, h) {
    super.frame(view, x, y, Math.min(w, 51), Math.min(h, 31));
  }
  measure() {
    return [51, 31];
  }
}

class SliderManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("input");
    el.type = "range";
    el.className = "pn-view pn-slider";
    el.step = "any";
    el.addEventListener("input", () => {
      this.fill(view);
      view.ctx.emit(view.tag, "on_change", [Number(el.value)]);
    });
    el.addEventListener("change", () => {
      if (view.hasEvent("on_sliding_complete")) view.ctx.emit(view.tag, "on_sliding_complete", [Number(el.value)]);
    });
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    if ("min_value" in changed) el.min = String(props.min_value ?? 0);
    if ("max_value" in changed) el.max = String(props.max_value ?? 1);
    if ("value" in changed && props.value != null) el.value = String(props.value);
    if ("minimum_track_color" in changed || "tint_color" in changed) {
      el.style.setProperty("--pn-fill-color", parseColor(props.minimum_track_color ?? props.tint_color, scheme) ?? "");
    }
    if ("maximum_track_color" in changed) el.style.setProperty("--pn-track", parseColor(props.maximum_track_color, scheme) ?? "");
    if ("thumb_color" in changed) el.style.setProperty("--pn-thumb", parseColor(props.thumb_color, scheme) ?? "");
    if ("disabled" in changed) el.disabled = props.disabled === true;
    this.fill(view);
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  /** The minimum track: the share of the range left of the thumb, painted in the tint. */
  fill(view) {
    const el = view.el;
    const min = Number(el.min) || 0;
    const max = Number(el.max);
    const span = max - min;
    const share = span > 0 ? Math.max(0, Math.min(1, (Number(el.value) - min) / span)) : 0;
    el.style.setProperty("--pn-fill", `${Math.round(share * 10000) / 100}%`);
  }
  measure(view, maxW) {
    return [isFiniteConstraint(maxW) ? Math.max(100, maxW) : 100, 34];
  }
}

class ActivityIndicatorManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    const spinner = document.createElement("div");
    spinner.className = "pn-spinner";
    el.appendChild(spinner);
    view.el = el;
    view.spinner = spinner;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const size = props.size === "large" ? 37 : 20;
    view.spinner.style.width = view.spinner.style.height = px(size);
    view.spinner.style.borderWidth = px(props.size === "large" ? 3 : 2);
    if ("color" in changed) view.spinner.style.borderTopColor = parseColor(props.color, scheme) ?? "#8e8e93";
    const animating = props.animating !== false;
    view.spinner.style.animationPlayState = animating ? "running" : "paused";
    view.spinner.style.visibility = !animating && props.hides_when_stopped !== false ? "hidden" : "";
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  measure(view) {
    const size = view.props.size === "large" ? 37 : 20;
    return [size, size];
  }
}

class ProgressBarManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    view.el = el;
    view.indeterminate = !!props.indeterminate;
    if (view.indeterminate) {
      const spinner = document.createElement("div");
      spinner.className = "pn-spinner";
      spinner.style.width = spinner.style.height = "20px";
      el.appendChild(spinner);
      view.spinner = spinner;
    } else {
      el.classList.add("pn-progress");
      const bar = document.createElement("div");
      el.appendChild(bar);
      view.bar = bar;
    }
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const color = parseColor(props.color, scheme);
    if (view.bar) {
      const value = Math.max(0, Math.min(1, Number(props.value ?? props.progress) || 0));
      view.bar.style.width = `${value * 100}%`;
      view.bar.style.backgroundColor = color ?? "";
      view.el.style.backgroundColor = parseColor(props.track_color, scheme) ?? "";
    } else if (view.spinner) {
      view.spinner.style.borderTopColor = color ?? "#8e8e93";
    }
    applyStyle(view, props, changed, scheme, { leaf: true, background: false });
  }
  measure(view, maxW) {
    if (view.indeterminate) return [20, 20];
    return [isFiniteConstraint(maxW) ? maxW : 100, 4];
  }
}

/** The `ScrollEvent` payload every renderer sends: offset, content size, and viewport size. */
export function scrollPayload(el) {
  return {
    x: el.scrollLeft,
    y: el.scrollTop,
    content_width: el.scrollWidth,
    content_height: el.scrollHeight,
    viewport_width: el.clientWidth,
    viewport_height: el.clientHeight,
  };
}

const SCROLL_IDLE_MS = 150;
// Pull to refresh, in points: the pull that fires `on_refresh`, the
// offset the spinner holds while refreshing, and the rubber band's limit.
const REFRESH_THRESHOLD = 64;
const REFRESH_HOLD = 56;
const REFRESH_MAX = 140;
const REFRESH_SETTLE_MS = 280;
const TEXT_CONTROL = "input, textarea, select, [contenteditable]";

/** The focused text control, if any (what `Keyboard.dismiss` and `keyboard_dismiss_mode` act on). */
function focusedTextControl() {
  const active = document.activeElement;
  return active && active.matches?.(TEXT_CONTROL) ? active : null;
}

/**
 * `snap_to_interval` / `snap_to_alignment`: the offset the scroller should
 * settle on, or `null` when snapping is off.
 */
export function snapTarget(offset, interval, alignment, viewport, range) {
  const step = Number(interval) || 0;
  if (step <= 0) return null;
  const shift = alignment === "center" ? (viewport - step) / 2 : alignment === "end" ? viewport - step : 0;
  const n = Math.round((offset + shift) / step);
  const target = n * step - shift;
  return Math.max(0, Math.min(Math.max(0, range - viewport), target));
}

class ScrollViewManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-scroll";
    const content = document.createElement("div");
    content.className = "pn-scroll-content";
    el.appendChild(content);
    view.el = el;
    view.content = content;
    view.lastScrollEmit = 0;
    view.scrollIdleTimer = null;
    view.pointerDown = false; // a pointer is held on the scroller
    view.dragging = false; // the content moved while the pointer was held
    view.moving = false; // any scrolling since the last settle
    view.snapping = false; // a programmatic snap is in flight
    const emit = (name, payload) => { if (view.hasEvent(name)) view.ctx.emit(view.tag, name, [payload]); };
    // The scroller came to rest: close the drag, snap if asked, then report
    // the final offset and the end of momentum.
    const settle = () => {
      clearTimeout(view.scrollIdleTimer);
      view.scrollIdleTimer = null;
      if (!view.moving) return;
      const payload = scrollPayload(el);
      if (view.dragging) {
        view.dragging = false;
        emit("on_scroll_end_drag", payload);
      }
      if (!view.snapping && this.snap(view) != null) return; // settles again once the snap lands
      view.moving = false;
      view.snapping = false;
      view.ctx.emit(view.tag, "on_scroll", [payload]);
      emit("on_momentum_scroll_end", payload);
    };
    view.settle = settle;
    el.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      view.pointerDown = true;
      this.handleTap(view, event);
    });
    const release = () => {
      if (!view.pointerDown) return;
      view.pointerDown = false;
      if (view.dragging) {
        view.dragging = false;
        emit("on_scroll_end_drag", scrollPayload(el));
      }
    };
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
    el.addEventListener("mousedown", (event) => this.keepFocus(view, event));
    el.addEventListener(
      "scroll",
      () => {
        if (view.snapping) {
          // The smooth snap is still moving; settle once it stops.
          clearTimeout(view.scrollIdleTimer);
          view.scrollIdleTimer = setTimeout(settle, SCROLL_IDLE_MS);
          return;
        }
        const props = view.props;
        const payload = scrollPayload(el);
        if (!view.moving) {
          view.moving = true;
          // Wheel and trackpad scrolling has no pointer; treat the first
          // movement as the drag React Native would report for a finger.
          view.dragging = true;
          emit("on_scroll_begin_drag", payload);
          if (props.keyboard_dismiss_mode === "on_drag") focusedTextControl()?.blur();
        }
        const throttle = Number(props.scroll_event_throttle) || 0;
        const now = performance.now();
        if (throttle <= 0 || now - view.lastScrollEmit >= throttle) {
          view.lastScrollEmit = now;
          view.ctx.emit(view.tag, "on_scroll", [payload]);
        }
        clearTimeout(view.scrollIdleTimer);
        view.scrollIdleTimer = setTimeout(settle, SCROLL_IDLE_MS);
      },
      { passive: true },
    );
    // Chrome fires `scrollend` once momentum stops; the idle timer covers the rest.
    el.addEventListener("scrollend", () => { if (!view.pointerDown) settle(); });
    this.update(view, props);
  }
  container(view) {
    return view.content;
  }
  /**
   * `keyboard_should_persist_taps`: `never` (the default) blurs the focused
   * input on a tap anywhere else in the scroller; `always` keeps it;
   * `handled` keeps it only when the tap landed on a control that handles
   * presses (a `Pressable`, `Button`, or another input).
   */
  handleTap(view, event) {
    const target = event.target;
    if (target.closest?.(TEXT_CONTROL)) return;
    const focused = focusedTextControl();
    if (!focused) return;
    const mode = view.props.keyboard_should_persist_taps || "never";
    if (mode === "never") focused.blur();
  }
  /** Stop the browser's default focus loss on `mousedown` when the taps should persist. */
  keepFocus(view, event) {
    const mode = view.props.keyboard_should_persist_taps || "never";
    if (mode === "never" || !focusedTextControl() || event.target.closest?.(TEXT_CONTROL)) return;
    const handled = !!event.target.closest?.(".pn-pressable, .pn-button, button, .pn-span-pressable, .pn-text-pressable");
    if (mode === "always" || (mode === "handled" && handled)) event.preventDefault();
  }
  /** Programmatic snap after the finger lifts; returns the target offset or `null`. */
  snap(view) {
    const props = view.props;
    const el = view.el;
    const horizontal = !!props.horizontal;
    const offset = horizontal ? el.scrollLeft : el.scrollTop;
    const target = snapTarget(
      offset,
      props.snap_to_interval,
      props.snap_to_alignment || "start",
      horizontal ? el.clientWidth : el.clientHeight,
      horizontal ? el.scrollWidth : el.scrollHeight,
    );
    if (target == null || Math.abs(target - offset) < 0.5) return null;
    view.snapping = true;
    el.scrollTo({ [horizontal ? "left" : "top"]: target, behavior: "smooth" });
    // The scroll events of the smooth animation keep pushing the settle
    // out; this timer covers a scroller that produces none.
    clearTimeout(view.scrollIdleTimer);
    view.scrollIdleTimer = setTimeout(view.settle, SCROLL_IDLE_MS * 3);
    return target;
  }
  applyOverflow(view) {
    const props = view.props;
    const el = view.el;
    if (props.scroll_enabled === false) {
      // Inline overflow wins over the class, so `scroll_enabled=False` is set here too.
      el.style.overflowX = el.style.overflowY = "hidden";
      return;
    }
    el.style.overflowX = props.horizontal ? "auto" : "hidden";
    el.style.overflowY = props.horizontal ? "hidden" : "auto";
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("shows_scroll_indicator")) el.classList.toggle("pn-no-indicator", props.shows_scroll_indicator === false);
    if (has("paging_enabled")) el.classList.toggle("pn-paging", !!props.paging_enabled);
    if (has("scroll_enabled")) el.classList.toggle("pn-scroll-disabled", props.scroll_enabled === false);
    if (has("content_inset")) {
      const inset = props.content_inset || {};
      view.content.style.padding = `${px(Number(inset.top) || 0)} ${px(Number(inset.right) || 0)} ${px(Number(inset.bottom) || 0)} ${px(Number(inset.left) || 0)}`;
    }
    // `deceleration_rate` tunes UIScrollView / OverScroller physics and
    // `bounces` the iOS rubber band; the browser owns both, so neither is
    // applied here.
    if (has("refresh_control")) this.updateRefresh(view);
    applyStyle(view, props, changed, scheme);
    if (has("overflow") && props.overflow !== "hidden") el.style.overflow = "";
    if (has("horizontal") || has("overflow") || has("scroll_enabled")) this.applyOverflow(view);
  }
  /**
   * `refresh_control`: pulling the content down past the threshold at the top
   * of the scroller (a trackpad or wheel scroll up, a mouse drag, or a touch
   * drag) fires `on_refresh`, and the spinner stays in view while Python
   * holds `refreshing` true, like UIRefreshControl and SwipeRefreshLayout.
   */
  updateRefresh(view) {
    const rc = view.props.refresh_control;
    if (!rc || typeof rc !== "object") {
      if (view.refresh) {
        view.refresh.remove();
        view.refresh = null;
        this.setPull(view, 0, false);
      }
      return;
    }
    if (!view.refresh) {
      const bar = document.createElement("div");
      bar.className = "pn-refresh";
      bar.setAttribute("aria-hidden", "true");
      const spinner = document.createElement("div");
      spinner.className = "pn-spinner pn-refresh-spinner";
      bar.appendChild(spinner);
      view.el.insertBefore(bar, view.content);
      view.refresh = bar;
      view.refreshSpinner = spinner;
      view.pull = 0;
      if (!view.pullInstalled) this.installPull(view);
    }
    const refreshing = !!rc.refreshing;
    const wasRefreshing = !!view.refreshing;
    view.refreshing = refreshing;
    const tint = parseColor(rc.tint_color ?? rc.color, view.ctx.scheme());
    view.refreshSpinner.style.borderTopColor = tint ?? "";
    if (refreshing) {
      clearTimeout(view.refreshFallback);
      view.refreshSpinner.classList.add("pn-refresh-spinning");
      if (!view.pulling) this.setPull(view, REFRESH_HOLD, true);
    } else if (wasRefreshing || (view.refreshTriggered && !view.pulling)) {
      this.retract(view);
    }
  }
  /** Offset the content by `distance` and reveal the spinner in proportion. */
  setPull(view, distance, animated) {
    view.pull = distance;
    const content = view.content;
    content.style.transition = animated ? `transform ${REFRESH_SETTLE_MS}ms cubic-bezier(0.2, 0.8, 0.2, 1)` : "";
    content.style.transform = distance > 0 ? `translateY(${px(distance)})` : "";
    const bar = view.refresh;
    if (!bar) return;
    const progress = Math.min(1, distance / REFRESH_THRESHOLD);
    bar.style.transition = content.style.transition.replace("transform", "opacity");
    bar.style.opacity = String(progress);
    bar.style.height = px(Math.max(distance, 0));
    if (!view.refreshing) view.refreshSpinner.style.transform = `rotate(${Math.round(progress * 270)}deg)`;
  }
  /** Spring the content back once the refresh is over (or never started). */
  retract(view) {
    clearTimeout(view.refreshFallback);
    view.refreshTriggered = false;
    view.refreshSpinner?.classList.remove("pn-refresh-spinning");
    this.setPull(view, 0, true);
  }
  /** The finger (or wheel) let go: hold the spinner if the pull fired, otherwise spring back. */
  releasePull(view) {
    view.pulling = false;
    if (view.refreshing) {
      this.setPull(view, REFRESH_HOLD, true);
    } else if (view.refreshTriggered) {
      // Python usually answers `on_refresh` by setting `refreshing`; keep
      // the spinner up briefly so a synchronous refresh still reads as one.
      this.setPull(view, REFRESH_HOLD, true);
      view.refreshSpinner.classList.add("pn-refresh-spinning");
      clearTimeout(view.refreshFallback);
      view.refreshFallback = setTimeout(() => { if (!view.refreshing) this.retract(view); }, 600);
    } else {
      this.setPull(view, 0, true);
    }
  }
  /** Track a pull by `delta` points (positive pulls down); fires `on_refresh` once past the threshold. */
  dragPull(view, delta) {
    if (!view.refresh || view.refreshing) return false;
    const next = Math.max(0, Math.min(REFRESH_MAX, view.pull + delta * (view.pull > REFRESH_THRESHOLD ? 0.3 : 0.55)));
    if (next === view.pull && next === 0) return false;
    view.pulling = true;
    this.setPull(view, next, false);
    if (next >= REFRESH_THRESHOLD && !view.refreshTriggered) {
      view.refreshTriggered = true;
      view.ctx.emit(view.tag, "on_refresh", []);
    }
    return true;
  }
  installPull(view) {
    view.pullInstalled = true;
    const el = view.el;
    const atTop = () => el.scrollTop <= 0 && !view.props.horizontal;
    // Frame points per client pixel: the device frame may be scaled down to fit.
    const scale = () => (el.clientHeight ? el.getBoundingClientRect().height / el.clientHeight : 1) || 1;
    let wheelTimer = null;
    el.addEventListener("wheel", (event) => {
      if (!view.refresh || view.refreshing || event.ctrlKey) return;
      const delta = -event.deltaY * (event.deltaMode === 1 ? 16 : 1);
      if (!(atTop() && delta > 0) && !(view.pull > 0 && view.pulling)) return;
      if (!this.dragPull(view, delta)) return;
      event.preventDefault();
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => this.releasePull(view), 140);
    }, { passive: false });
    // Mouse and pen: dragging the content down while it rests at the top.
    let drag = null;
    el.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch" || event.button !== 0 || !view.refresh || !atTop()) return;
      drag = { y: event.clientY, last: 0, active: false, id: event.pointerId };
    });
    el.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const travel = (event.clientY - drag.y) / scale();
      if (!drag.active) {
        if (travel < 6) return;
        drag.active = true;
        drag.last = travel;
        el.setPointerCapture?.(event.pointerId);
      }
      this.dragPull(view, travel - drag.last);
      drag.last = travel;
    });
    const endDrag = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const active = drag.active;
      drag = null;
      if (!active) return;
      // The drag shouldn't also count as a tap on whatever it started on.
      el.addEventListener("click", (click) => { click.stopPropagation(); click.preventDefault(); }, { capture: true, once: true });
      setTimeout(() => this.releasePull(view), 0);
    };
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    // Touch: a downward drag at the top pulls instead of scrolling.
    let touch = null;
    el.addEventListener("touchstart", (event) => {
      touch = view.refresh && atTop() && event.touches.length === 1 ? { y: event.touches[0].clientY, last: 0 } : null;
    }, { passive: true });
    el.addEventListener("touchmove", (event) => {
      if (!touch) return;
      const travel = (event.touches[0].clientY - touch.y) / scale();
      if (travel <= 0 && !view.pulling) return;
      if (this.dragPull(view, travel - touch.last)) event.preventDefault();
      touch.last = travel;
    }, { passive: false });
    const endTouch = () => {
      if (touch && view.pulling) this.releasePull(view);
      touch = null;
    };
    el.addEventListener("touchend", endTouch);
    el.addEventListener("touchcancel", endTouch);
  }
  childrenChanged(view) {
    // Content size = union of the children's frames (as UIScrollView.contentSize).
    let w = 0;
    let h = 0;
    for (const child of view.children) {
      if (!child.frame) continue;
      w = Math.max(w, child.frame.x + child.frame.w);
      h = Math.max(h, child.frame.y + child.frame.h);
    }
    view.content.style.width = w ? px(w) : "";
    view.content.style.height = h ? px(h) : "";
  }
  command(view, name, args) {
    const el = view.el;
    const animated = args.animated !== false;
    const behavior = animated ? "smooth" : "auto";
    switch (name) {
      case "scroll_to_offset":
        el.scrollTo({ left: Number(args.x) || 0, top: Number(args.y) || 0, behavior });
        return null;
      case "scroll_to_end":
        el.scrollTo({ left: el.scrollWidth, top: el.scrollHeight, behavior });
        return null;
      case "get_scroll_offset":
        return { x: el.scrollLeft, y: el.scrollTop };
      case "flash_scroll_indicators":
        return null;
      default:
        return null;
    }
  }
}

class PressableManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-pressable";
    view.el = el;
    view.pressed = false;
    view.longPressTimer = null;
    view.longPressed = false;
    const enabled = () => !view.props.disabled;
    const setPressed = (on) => {
      view.pressed = on;
      view.pressedOpacityActive = on;
      const pressedOpacity = view.props.pressed_opacity != null ? Number(view.props.pressed_opacity) : 0.6;
      el.style.opacity = on ? String(pressedOpacity) : view.props.opacity != null ? String(view.props.opacity) : "";
    };
    el.addEventListener("pointerdown", (event) => {
      if (!enabled() || event.button !== 0) return;
      event.stopPropagation();
      view.longPressed = false;
      setPressed(true);
      try {
        el.setPointerCapture(event.pointerId);
      } catch (err) {
        /* ignore */
      }
      view.ctx.emit(view.tag, "on_press_in", []);
      if (view.hasEvent("on_long_press")) {
        const delay = Math.max(50, Number(view.props.delay_long_press) || 500);
        view.longPressTimer = setTimeout(() => {
          view.longPressed = true;
          view.ctx.emit(view.tag, "on_long_press", []);
        }, delay);
      }
    });
    const finish = (event, fire) => {
      if (!view.pressed) return;
      clearTimeout(view.longPressTimer);
      setPressed(false);
      view.ctx.emit(view.tag, "on_press_out", []);
      if (fire && !view.longPressed && enabled()) view.ctx.emit(view.tag, "on_press", []);
    };
    el.addEventListener("pointerup", (event) => {
      event.stopPropagation();
      const rect = el.getBoundingClientRect();
      const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
      finish(event, inside);
    });
    el.addEventListener("pointercancel", (event) => finish(event, false));
    el.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && enabled()) {
        event.preventDefault();
        view.ctx.emit(view.tag, "on_press", []);
      }
    });
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const disabled = !!props.disabled;
    // `disabled` suppresses every press callback (see `enabled()` above),
    // drops the pressed styling, and exposes the disabled state.
    view.el.classList.toggle("pn-disabled", disabled);
    view.el.tabIndex = disabled || view.importance === "no" ? -1 : 0;
    if (disabled) view.el.setAttribute("aria-disabled", "true");
    else if (!(props.accessibility_state && props.accessibility_state.disabled)) view.el.removeAttribute("aria-disabled");
    if (disabled && view.pressed) {
      clearTimeout(view.longPressTimer);
      view.pressed = false;
      view.pressedOpacityActive = false;
      view.el.style.opacity = props.opacity != null ? String(props.opacity) : "";
    }
    // `android_ripple` is a Material ripple; iOS and the browser ignore it.
    applyStyle(view, props, changed, view.ctx.scheme());
  }
}

class CheckboxManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-checkbox";
    el.setAttribute("role", "checkbox");
    const box = document.createElement("div");
    box.className = "pn-box";
    box.textContent = "✓";
    const label = document.createElement("span");
    el.appendChild(box);
    el.appendChild(label);
    el.addEventListener("click", () => {
      if (view.props.disabled) return;
      view.ctx.emit(view.tag, "on_change", [!view.props.value]);
    });
    view.el = el;
    view.label = label;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    view.el.classList.toggle("pn-on", !!props.value);
    view.el.setAttribute("aria-checked", String(!!props.value));
    view.el.classList.toggle("pn-disabled", !!props.disabled);
    if ("label" in changed) view.label.textContent = props.label == null ? "" : String(props.label);
    if ("color" in changed) view.el.style.setProperty("--pn-check", parseColor(props.color, scheme) ?? "");
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
  }
  measure(view, maxW, maxH) {
    const [w, h] = measureElement(view.el, maxW, maxH);
    return [w, Math.max(24, h)];
  }
}

class SegmentedControlManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-segmented";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    if ("segments" in changed || "selected_index" in changed || "disabled" in changed || "tint_color" in changed) {
      el.textContent = "";
      const segments = Array.isArray(props.segments) ? props.segments : [];
      segments.forEach((label, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(label);
        button.disabled = props.disabled === true;
        if (index === Number(props.selected_index)) {
          button.classList.add("pn-selected");
          const tint = parseColor(props.tint_color, scheme);
          if (tint) button.style.backgroundColor = tint;
        }
        button.addEventListener("click", () => view.ctx.emit(view.tag, "on_change", [index]));
        el.appendChild(button);
      });
    }
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
  }
  measure(view, maxW) {
    const [w] = measureElement(view.el, maxW, INF);
    return [isFiniteConstraint(maxW) ? Math.min(Math.max(w, 120), maxW) : Math.max(w, 120), 32];
  }
}

class PickerManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("select");
    el.className = "pn-view pn-select";
    el.addEventListener("change", () => {
      const item = (view.props.items || [])[el.selectedIndex - (view.hasPlaceholder ? 1 : 0)];
      view.ctx.emit(view.tag, "on_change", [item ? item.value : null]);
    });
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    if ("items" in changed || "placeholder" in changed || "value" in changed) {
      el.textContent = "";
      view.hasPlaceholder = props.placeholder != null;
      if (view.hasPlaceholder) {
        const opt = document.createElement("option");
        opt.textContent = String(props.placeholder);
        opt.disabled = true;
        opt.selected = props.value == null;
        el.appendChild(opt);
      }
      for (const item of Array.isArray(props.items) ? props.items : []) {
        const opt = document.createElement("option");
        opt.textContent = String(item.label ?? item.value ?? "");
        opt.selected = props.value != null && String(item.value) === String(props.value);
        el.appendChild(opt);
      }
    }
    applyStyle(view, props, changed, view.ctx.scheme(), { leaf: true });
    view.measureCache = null;
  }
  measure(view, maxW) {
    const [w] = measureElement(view.el, maxW, INF);
    return [Math.max(100, w), 36];
  }
}

class DatePickerManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("input");
    el.className = "pn-view pn-date";
    el.addEventListener("change", () => view.ctx.emit(view.tag, "on_change", [el.value]));
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const mode = props.mode || "date";
    el.type = mode === "time" ? "time" : mode === "datetime" ? "datetime-local" : "date";
    if ("value" in changed && props.value != null) el.value = String(props.value);
    if ("minimum" in changed) el.min = props.minimum == null ? "" : String(props.minimum);
    if ("maximum" in changed) el.max = props.maximum == null ? "" : String(props.maximum);
    if ("disabled" in changed) el.disabled = props.disabled === true;
    if ("tint_color" in changed) el.style.accentColor = parseColor(props.tint_color, view.ctx.scheme()) ?? "";
    applyStyle(view, props, changed, view.ctx.scheme(), { leaf: true });
  }
  measure() {
    return [160, 36];
  }
}

class TabBarManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-tabbar";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    el.textContent = "";
    const items = Array.isArray(props.items) ? props.items : [];
    const activeName = props.active_tab;
    // The `TabBar` contract's styling props: `tint_color`,
    // `inactive_tint_color`, `background_color`, `translucent`, `shows_labels`.
    el.style.setProperty("--pn-tab-active", parseColor(props.tint_color, scheme) ?? "");
    const inactive = parseColor(props.inactive_tint_color, scheme);
    el.classList.toggle("pn-opaque", props.translucent === false);
    el.classList.toggle("pn-no-labels", props.shows_labels === false);
    el.style.paddingBottom = px(view.ctx.bottomInset());
    items.forEach((item, index) => {
      const name = item.name ?? item.title ?? String(index);
      const button = document.createElement("button");
      button.type = "button";
      const active = activeName != null && name === activeName;
      button.classList.toggle("pn-active", active);
      if (!active && inactive) button.style.color = inactive;
      const icon = document.createElement("span");
      icon.className = "pn-tab-icon";
      icon.appendChild(tabIcon(item.icon));
      const label = document.createElement("span");
      label.textContent = String(item.title ?? name);
      button.appendChild(icon);
      button.appendChild(label);
      if (item.badge != null && item.badge !== "") {
        const badge = document.createElement("span");
        badge.className = "pn-badge";
        badge.textContent = String(item.badge);
        button.appendChild(badge);
      }
      button.addEventListener("click", () => view.ctx.emit(view.tag, "on_tab_select", [name]));
      el.appendChild(button);
    });
    applyStyle(view, props, changed, scheme);
    if ("background_color" in changed && props.background_color == null) el.style.backgroundColor = "";
  }
  measure(view, maxW) {
    return [isFiniteConstraint(maxW) ? maxW : view.ctx.frameWidth(), 49 + view.ctx.bottomInset()];
  }
}

/**
 * Build the icon node for a tab item: an inline SVG for a bundled icon
 * spec (`{shapes, view_box}`), a tinted mask for an asset (`{uri}`), or a
 * dot when the tab has no icon.
 */
function tabIcon(icon) {
  if (icon && typeof icon === "object" && Array.isArray(icon.shapes)) {
    const svg = buildSvg(icon.shapes, {
      view_box: icon.view_box || "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      stroke_width: 2,
      stroke_linecap: "round",
      stroke_linejoin: "round",
    });
    svg.setAttribute("width", "24");
    svg.setAttribute("height", "24");
    return svg;
  }
  if (icon && typeof icon === "object" && icon.uri) {
    const mask = document.createElement("span");
    mask.className = "pn-tab-icon-mask";
    const url = imageSource(icon.uri);
    mask.style.maskImage = mask.style.webkitMaskImage = url ? `url("${url}")` : "";
    return mask;
  }
  const dot = document.createElement("span");
  dot.textContent = "●";
  return dot;
}

// ---------------------------------------------------------------------------
// Svg, LinearGradient, BlurView
// ---------------------------------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";
const SVG_PAINT = {
  fill: "fill",
  fill_opacity: "fill-opacity",
  fill_rule: "fill-rule",
  stroke: "stroke",
  stroke_width: "stroke-width",
  stroke_opacity: "stroke-opacity",
  stroke_linecap: "stroke-linecap",
  stroke_linejoin: "stroke-linejoin",
  opacity: "opacity",
  transform: "transform",
};
const SVG_GEOMETRY = {
  path: ["d"],
  circle: ["cx", "cy", "r"],
  ellipse: ["cx", "cy", "rx", "ry"],
  rect: ["x", "y", "width", "height", "rx", "ry"],
  line: ["x1", "y1", "x2", "y2"],
  polyline: ["points"],
  polygon: ["points"],
};

function svgPaintValue(key, value, scheme) {
  if (value == null) return null;
  if (key === "fill" || key === "stroke") {
    if (value === "none" || value === "currentColor") return value;
    return parseColor(value, scheme) ?? String(value);
  }
  return String(value);
}

/** Build an `<svg>` element from flattened shape records and root paint. */
function buildSvg(shapes, root, scheme = "light") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("xmlns", SVG_NS);
  svg.setAttribute("viewBox", String(root.view_box || "0 0 24 24"));
  const par = root.preserve_aspect_ratio;
  svg.setAttribute("preserveAspectRatio", par === "slice" ? "xMidYMid slice" : par === "none" ? "none" : "xMidYMid meet");
  const rootFill = root.fill == null ? null : svgPaintValue("fill", root.fill, scheme);
  svg.setAttribute("fill", rootFill ?? "#000");
  for (const key of ["stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "fill_rule"]) {
    const value = svgPaintValue(key, root[key], scheme);
    if (value != null) svg.setAttribute(SVG_PAINT[key], value);
  }
  for (const shape of shapes || []) {
    const kind = String(shape.kind || "path");
    if (!(kind in SVG_GEOMETRY)) continue;
    const node = document.createElementNS(SVG_NS, kind);
    for (const attr of SVG_GEOMETRY[kind]) if (shape[attr] != null) node.setAttribute(attr, String(shape[attr]));
    for (const [key, attr] of Object.entries(SVG_PAINT)) {
      const value = svgPaintValue(key, shape[key], scheme);
      if (value != null) node.setAttribute(attr, value);
    }
    if (Array.isArray(shape.stroke_dasharray) && shape.stroke_dasharray.length) {
      node.setAttribute("stroke-dasharray", shape.stroke_dasharray.join(" "));
    }
    svg.appendChild(node);
  }
  return svg;
}

class SvgManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-svg";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const paintKeys = ["shapes", "view_box", "preserve_aspect_ratio", "fill", "stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "fill_rule", "color"];
    if (paintKeys.some((k) => k in changed) || !view.svg) {
      view.el.textContent = "";
      view.svg = buildSvg(props.shapes, props, scheme);
      view.svg.setAttribute("width", "100%");
      view.svg.setAttribute("height", "100%");
      view.el.appendChild(view.svg);
      view.measureCache = null;
    }
    if ("color" in changed) view.el.style.color = parseColor(props.color, scheme) ?? "";
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  refreshColors(view) {
    this.update(view, { shapes: view.props.shapes });
  }
}

class LinearGradientManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-gradient";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    if (["colors", "locations", "start_point", "end_point"].some((k) => k in changed) || !view.gradientApplied) {
      view.gradientApplied = true;
      view.el.style.backgroundImage = gradientCSS(props, scheme);
    }
    applyStyle(view, props, changed, scheme);
    // `background_color` would paint over the gradient; keep the image on top.
    if ("background_color" in changed) view.el.style.backgroundImage = gradientCSS(props, scheme);
  }
  refreshColors(view) {
    view.el.style.backgroundImage = gradientCSS(view.props, view.ctx.scheme());
  }
}

function gradientCSS(props, scheme) {
  const colors = Array.isArray(props.colors) ? props.colors.map((c) => parseColor(c, scheme) ?? "transparent") : [];
  if (colors.length < 2) return "";
  const start = Array.isArray(props.start_point) ? props.start_point : [0, 0];
  const end = Array.isArray(props.end_point) ? props.end_point : [0, 1];
  const dx = Number(end[0]) - Number(start[0]);
  const dy = Number(end[1]) - Number(start[1]);
  // CSS angles run clockwise from "to top"; (0,0)->(0,1) is 180deg.
  const angle = (Math.atan2(dx, -dy) * 180) / Math.PI;
  const locations = Array.isArray(props.locations) && props.locations.length === colors.length ? props.locations : null;
  const stops = colors.map((c, i) => (locations ? `${c} ${Math.round(Number(locations[i]) * 10000) / 100}%` : c));
  return `linear-gradient(${Math.round(angle * 100) / 100}deg, ${stops.join(", ")})`;
}

const LIGHT_TINT = "255, 255, 255";
const DARK_TINT = "28, 28, 30";

/** Tint color and opacity for each blur type; `null` follows the color scheme. */
function blurTint(type, scheme) {
  const dark = scheme === "dark";
  switch (type) {
    case "light":
      return [LIGHT_TINT, 0.55];
    case "extra_light":
      return [LIGHT_TINT, 0.75];
    case "dark":
      return [DARK_TINT, 0.6];
    case "prominent":
    case "system_thick_material":
      return dark ? [DARK_TINT, 0.75] : [LIGHT_TINT, 0.8];
    case "system_thin_material":
      return dark ? [DARK_TINT, 0.4] : [LIGHT_TINT, 0.45];
    default:
      return dark ? [DARK_TINT, 0.55] : [LIGHT_TINT, 0.6];
  }
}

class BlurViewManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-blur";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    if ("blur_type" in changed || "intensity" in changed || !view.blurApplied) {
      view.blurApplied = true;
      const intensity = Math.max(0, Math.min(100, props.intensity == null ? 100 : Number(props.intensity))) / 100;
      const type = String(props.blur_type || "regular");
      const radius = 20 * intensity;
      view.el.style.backdropFilter = view.el.style.webkitBackdropFilter = radius > 0 ? `blur(${px(radius)}) saturate(1.5)` : "";
      const [rgb, alpha] = blurTint(type, scheme);
      view.el.style.backgroundColor = `rgba(${rgb}, ${Math.round(alpha * intensity * 1000) / 1000})`;
    }
    applyStyle(view, props, changed, scheme);
    if ("background_color" in changed && props.background_color == null) this.update(view, { blur_type: props.blur_type });
  }
  refreshColors(view) {
    this.update(view, { blur_type: view.props.blur_type });
  }
}

class ModalManager extends ViewManager {
  create(view, props) {
    // The element in the tree is a zero-size placeholder; the content
    // lives in the overlay layer while `visible` is true.
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.display = "none";
    const backdrop = document.createElement("div");
    backdrop.className = "pn-modal-backdrop";
    const sheet = document.createElement("div");
    sheet.className = "pn-modal-sheet";
    backdrop.appendChild(sheet);
    // `on_request_close` is the browser's stand-in for the Android back
    // button and the iOS sheet pull-down: the backdrop tap and the Escape
    // key ask Python to close. Without the callback the modal stays open.
    const requestClose = () => {
      if (view.hasEvent("on_request_close")) view.ctx.emit(view.tag, "on_request_close", []);
    };
    backdrop.addEventListener("click", (event) => {
      // An overlay's sheet fills the backdrop, so its own empty area (not a
      // child) counts as the backdrop there.
      const overlay = view.props.presentation_style === "overlay" || !!view.props.transparent;
      if (event.target !== backdrop && !(overlay && event.target === sheet)) return;
      if (view.props.dismiss_on_backdrop === false) return;
      requestClose();
    });
    view.onKeyDown = (event) => {
      if (event.key !== "Escape" || !view.shown || event.defaultPrevented) return;
      // Only the topmost modal answers Escape.
      const layer = view.ctx.overlays();
      if (layer.lastElementChild !== view.backdrop) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      requestClose();
    };
    view.el = el;
    view.backdrop = backdrop;
    view.sheet = sheet;
    view.shown = false;
    this.update(view, props);
  }
  container(view) {
    return view.sheet;
  }
  /** The content lays out against the sheet once it's on stage (the core uses the window until then). */
  reportContainers(view, report) {
    if (view.shown) report(view.tag, view.sheet);
  }
  observed(view) {
    return [view.sheet];
  }
  frame() {}
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const style = props.presentation_style;
    const overlay = style === "overlay" || !!props.transparent;
    view.sheet.className = "pn-modal-sheet";
    if (style === "full_screen") view.sheet.classList.add("pn-full");
    else if (style === "form_sheet") view.sheet.classList.add("pn-form");
    if (overlay) view.sheet.classList.add("pn-overlay");
    view.backdrop.classList.toggle("pn-transparent", overlay);
    view.sheet.style.backgroundColor = !overlay ? (parseColor(props.background_color, scheme) ?? "") : "transparent";
    // `status_bar_translucent` lets Android draw under the status bar; the
    // preview's status bar is part of the frame chrome, so nothing to do.
    const visible = !!props.visible;
    if (visible && !view.shown) {
      view.shown = true;
      clearTimeout(view.leaving);
      view.backdrop.classList.remove("pn-modal-out");
      view.backdrop.style.pointerEvents = "";
      view.ctx.overlays().appendChild(view.backdrop);
      this.present(view);
      document.addEventListener("keydown", view.onKeyDown, true);
      view.ctx.emit(view.tag, "on_show", []);
    } else if (!visible && view.shown) {
      view.shown = false;
      this.dismiss(view, view.backdrop);
      document.removeEventListener("keydown", view.onKeyDown, true);
      view.ctx.emit(view.tag, "on_dismiss", []);
    }
  }
  /** `animation_type`: the sheet slides up (or fades in) over a fading backdrop. */
  present(view) {
    const kind = view.props.animation_type || "slide";
    if (kind === "none") return;
    const backdrop = view.backdrop;
    backdrop.dataset.animation = kind;
    backdrop.classList.add("pn-modal-out");
    void backdrop.offsetWidth; // commit the off-stage position before transitioning from it
    requestAnimationFrame(() => backdrop.classList.remove("pn-modal-out"));
  }
  /** Play the dismissal on `backdrop`, then take it off the stage. */
  dismiss(view, backdrop) {
    const kind = view.props.animation_type || "slide";
    if (kind === "none") {
      backdrop.remove();
      return;
    }
    backdrop.dataset.animation = kind;
    backdrop.style.pointerEvents = "none";
    backdrop.classList.add("pn-modal-out");
    view.leaving = setTimeout(() => {
      backdrop.remove();
      backdrop.style.pointerEvents = "";
    }, MODAL_TRANSITION_MS + 40);
  }
  destroy(view) {
    document.removeEventListener("keydown", view.onKeyDown, true);
    if (!view.shown) return;
    // Python destroys the content with the modal; animate a snapshot out.
    const ghost = view.backdrop.cloneNode(true);
    view.backdrop.replaceWith(ghost);
    this.dismiss(view, ghost);
  }
}

const MODAL_TRANSITION_MS = 300;

class PortalManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.display = "none";
    const layer = document.createElement("div");
    layer.className = "pn-view";
    layer.style.inset = "0";
    layer.style.width = layer.style.height = "100%";
    layer.style.pointerEvents = "none";
    view.el = el;
    view.layer = layer;
    view.ctx.overlays().appendChild(layer);
    this.update(view, props);
  }
  container(view) {
    return view.layer;
  }
  /** The portal's children lay out against the whole device frame, like a window-level overlay. */
  reportContainers(view, report) {
    report(view.tag, view.ctx.overlays());
  }
  observed(view) {
    return [view.ctx.overlays()];
  }
  frame() {}
  update() {}
  destroy(view) {
    view.layer.remove();
  }
  childrenChanged(view) {
    for (const child of view.children) child.el.style.pointerEvents = "auto";
  }
}

class StatusBarManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.display = "none";
    view.el = el;
    this.update(view, props);
  }
  frame() {}
  update(view) {
    const props = view.props;
    const style = props.bar_style;
    // `translucent` (Android draws under the bar) and `animated` (iOS
    // animates the change) don't apply to the frame's painted status bar.
    view.ctx.statusBar({
      hidden: !!props.hidden,
      light: style === "light" || style === "light_content",
      dark: style === "dark" || style === "dark_content",
    });
  }
}

class WebViewManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    const frame = document.createElement("iframe");
    frame.className = "pn-webview";
    frame.setAttribute("sandbox", "allow-scripts allow-forms allow-popups allow-same-origin");
    el.appendChild(frame);
    view.el = el;
    view.iframe = frame;
    frame.addEventListener("load", () => {
      let url = view.props.url || view.props.base_url || "about:srcdoc";
      try {
        url = frame.contentWindow.location.href;
      } catch (err) {
        /* cross-origin */
      }
      view.ctx.emit(view.tag, "on_load", [url]);
      if (view.hasEvent("on_navigation_state_change")) {
        view.ctx.emit(view.tag, "on_navigation_state_change", [{ url, loading: false, can_go_back: false, can_go_forward: false, title: "" }]);
      }
    });
    view.onMessage = (event) => {
      if (event.source !== frame.contentWindow) return;
      const data = event.data;
      view.ctx.emit(view.tag, "on_message", [typeof data === "string" ? data : JSON.stringify(data)]);
    };
    window.addEventListener("message", view.onMessage);
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    if ("url" in changed && props.url) {
      view.iframe.removeAttribute("srcdoc");
      view.iframe.src = String(props.url);
      if (view.hasEvent("on_load_start")) view.ctx.emit(view.tag, "on_load_start", [String(props.url)]);
    } else if ("html" in changed && props.html != null) {
      const shim =
        "<script>window.webkit={messageHandlers:{pythonnative:{postMessage:function(m){parent.postMessage(m,'*');}}}};</script>";
      view.iframe.srcdoc = shim + String(props.html);
    }
    if ("scroll_enabled" in changed) view.iframe.style.overflow = props.scroll_enabled === false ? "hidden" : "";
    applyStyle(view, props, changed, view.ctx.scheme(), { leaf: true });
  }
  command(view, name, args) {
    const win = view.iframe.contentWindow;
    try {
      switch (name) {
        case "inject_javascript":
          win.eval(String(args.script ?? ""));
          return null;
        case "reload":
          win.location.reload();
          return null;
        case "go_back":
          win.history.back();
          return null;
        case "go_forward":
          win.history.forward();
          return null;
        case "stop_loading":
          win.stop();
          return null;
        case "load_url":
          view.iframe.src = String(args.url || "");
          return null;
        case "get_url":
          return win.location.href;
        case "can_go_back":
        case "can_go_forward":
          return false;
        default:
          return null;
      }
    } catch (err) {
      return null;
    }
  }
  destroy(view) {
    window.removeEventListener("message", view.onMessage);
  }
}

/**
 * `VirtualList`: the core holds the dataset (keys, extents, and sticky
 * flags), validated in the commit and published here with
 * `pn_core_list_apply` when a mount carries a `dataset` patch. Python binds
 * row roots for the window this list reports (`on_window`); each row is a
 * detached root the core lays out at the list's width, and the list stacks
 * them at prefix-sum offsets of their measured (or declared) extents.
 */
class VirtualListManager extends ViewManager {
  create(view, props) {
    view.el = document.createElement("div"); view.el.className = "pn-view pn-vlist";
    view.spacer = document.createElement("div"); view.spacer.className = "pn-vlist-spacer";
    view.el.appendChild(view.spacer);
    view.rows = {revision: 0, keys: [], extents: [], sticky: [], indices: new Map(), measured: new Map(), offsets: [0], dirty: false};
    view.lastWindow = "";
    view.el.addEventListener("scroll", () => {
      this.childrenChanged(view);
      if (view.hasEvent("on_scroll")) view.ctx.emit(view.tag, "on_scroll", [scrollPayload(view.el)]);
    }, {passive:true});
    this.update(view, props);
  }
  container(view) { return view.spacer; }
  update(view, changed) {
    super.update(view, changed);
    view.el.style.overflow = "auto";
    if ("dataset" in changed) this.publish(view);
    this.childrenChanged(view);
  }
  /** Apply the dataset patch the core published with this mount, keeping the first visible row in place. */
  publish(view) {
    const rows = view.rows, horizontal = !!view.props.horizontal;
    const offset = horizontal ? view.el.scrollLeft : view.el.scrollTop;
    const first = this.indexAt(view, offset), anchor = rows.keys[first], delta = offset - (rows.offsets[first] || 0);
    const core = view.ctx.list?.();
    if (!core) return;
    const surface = view.ctx.surface(), tag = view.tag;
    const patch = core.listApply(surface, tag);
    // A recreated list view starts from the dataset the core already holds.
    rows.revision = patch ? Number(patch.revision) : core.listRevision(surface, tag);
    if (patch?.reset) rows.measured.clear();
    const count = core.listCount(surface, tag);
    rows.keys = new Array(count); rows.extents = new Array(count); rows.sticky = [];
    for (let i = 0; i < count; i++) {
      rows.keys[i] = core.listKey(surface, tag, i);
      rows.extents[i] = core.listExtent(surface, tag, i);
      if (core.listSticky(surface, tag, i)) rows.sticky.push(i);
    }
    rows.indices = new Map(rows.keys.map((key, i) => [key, i]));
    for (const key of [...rows.measured.keys()]) if (!rows.indices.has(key)) rows.measured.delete(key);
    this.reindex(view);
    if (anchor != null && rows.indices.has(anchor)) view.el[horizontal ? "scrollLeft" : "scrollTop"] = rows.offsets[rows.indices.get(anchor)] + delta;
  }
  /** Prefix sums of the row extents: a row's measured size once it laid out, else its declared extent. */
  reindex(view) {
    const rows = view.rows, offsets = new Array(rows.keys.length + 1);
    offsets[0] = 0;
    for (let i = 0; i < rows.keys.length; i++) offsets[i + 1] = offsets[i] + (rows.measured.get(rows.keys[i]) ?? rows.extents[i]);
    rows.offsets = offsets;
    rows.dirty = false;
  }
  indexAt(view, offset) {
    const offsets = view.rows.offsets, count = view.rows.keys.length;
    let low = 0, high = Math.max(0, count - 1);
    while (low < high) { const mid = (low + high + 1) >>> 1; if (offsets[mid] <= offset) low = mid; else high = mid - 1; }
    return low;
  }
  childrenChanged(view) {
    const rows = view.rows; if (!rows) return;
    const horizontal = !!view.props.horizontal;
    const offset = horizontal ? view.el.scrollLeft : view.el.scrollTop;
    const extent = (horizontal ? view.el.clientWidth : view.el.clientHeight) || 800;
    const oldFirst = this.indexAt(view, offset), anchor = rows.keys[oldFirst], anchorDelta = offset - (rows.offsets[oldFirst] || 0);
    for (const child of view.children) {
      const key = child.props._pn_list_key, size = child.frame?.[horizontal ? "w" : "h"];
      if (!rows.indices.has(key) || !(size > 0)) continue;
      const before = rows.measured.get(key) ?? rows.extents[rows.indices.get(key)];
      if (Math.abs(before - size) >= 0.01) { rows.measured.set(key, size); rows.dirty = true; }
    }
    if (rows.dirty) this.reindex(view);
    const anchoredOffset = anchor == null ? offset : rows.offsets[rows.indices.get(anchor)] + anchorDelta;
    if (Math.abs(anchoredOffset - offset) > 0.5) view.el[horizontal ? "scrollLeft" : "scrollTop"] = anchoredOffset;
    view.first = this.indexAt(view, anchoredOffset); view.last = rows.keys.length ? this.indexAt(view, anchoredOffset + extent) : -1;
    const core = view.ctx.list?.();
    const sticky = horizontal || !rows.keys.length || !core ? -1 : core.listStickyAt(view.ctx.surface(), view.tag, view.first);
    const nextSticky = rows.sticky.find(index => index > sticky);
    for (const child of view.children) {
      const index = rows.indices.get(child.props._pn_list_key);
      if (index == null) { child.el.style.display = "none"; continue; }
      let position = rows.offsets[index];
      if (index === sticky) {
        const size = rows.offsets[index + 1] - position;
        position = Math.min(anchoredOffset, nextSticky == null ? Infinity : rows.offsets[nextSticky] - size);
      }
      child.el.style.display = "";
      child.el.style[horizontal ? "left" : "top"] = px(position);
      child.el.style[horizontal ? "top" : "left"] = "0px";
      child.el.style.zIndex = index === sticky ? "1024" : "";
    }
    const range = rows.offsets[rows.keys.length];
    view.spacer.style[horizontal ? "width" : "height"] = px(range);
    const identity = [rows.revision, view.first, view.last, extent, sticky].join(":");
    if (identity !== view.lastWindow) {
      view.lastWindow = identity;
      view.ctx.emit(view.tag, "on_window", [{...scrollPayload(view.el), first:view.first, last:view.last, extent, range, sticky, revision:rows.revision}]);
    }
  }
  command(view, name, args) {
    if (name === "get_scroll_offset") return {x:view.el.scrollLeft, y:view.el.scrollTop};
    if (name === "flash_scroll_indicators") return null;
    const horizontal = !!view.props.horizontal;
    let offset = args[horizontal ? "x" : "y"] || 0;
    if (name === "scroll_to_end") offset = horizontal ? view.el.scrollWidth : view.el.scrollHeight;
    if (name === "scroll_to_index") offset = view.rows.offsets[Math.max(0, Math.min(Number(args.index) || 0, view.rows.keys.length))];
    view.el.scrollTo({[horizontal ? "left" : "top"]: offset, behavior: args.animated ? "smooth" : "instant"});
    return null;
  }
}

const SCREEN_TRANSITION_MS = 260;
const MODAL_PRESENTATIONS = new Set(["modal", "full_screen_modal", "form_sheet", "transparent_modal"]);

/**
 * The entering/leaving CSS class for a `Screen`'s `animation` and
 * `presentation` props: `default` slides from the right for cards and from
 * the bottom for the modal presentations; `none` skips the transition.
 */
/**
 * Jump `el` to a transition's start state (`cls`) without animating there,
 * and commit that style so removing `cls` afterwards plays the transition.
 */
export function placeOffStage(el, cls) {
  el.style.transition = "none";
  el.classList.add(cls);
  void getComputedStyle(el).transform;
  el.style.transition = "";
}

export function screenTransition(props) {
  const animation = props?.animation || "default";
  if (animation === "none") return null;
  if (animation === "fade") return "pn-screen-fade";
  if (animation === "slide_from_bottom") return "pn-screen-bottom";
  if (animation === "slide_from_right") return "pn-screen-right";
  return MODAL_PRESENTATIONS.has(props?.presentation) ? "pn-screen-bottom" : "pn-screen-right";
}

/**
 * The native stack container. Only the topmost `Screen` is shown, with the
 * screen beneath a `transparent_modal` kept visible under it. Pushes slide
 * or fade the new screen in; pops animate a snapshot of the removed screen
 * out, since Python destroys the real views in the same transaction.
 *
 * Like `UINavigationController` and the Android toolbar, the stack draws a
 * navigation bar from the top screen's options (`title`, `header_shown`,
 * `header_large_title`, `header_back_visible`, `header_tint_color`,
 * `header_style`, `header_title_style`) and hosts its `header_left` /
 * `header_right` slot views. The back button reports `on_native_back`, so
 * Python pops the route (or vetoes it through `before_remove`) exactly as
 * it does for an iOS swipe back.
 */
class ScreenStackManager extends ViewManager {
  create(view, props) {
    super.create(view, props);
    view.el.classList.add("pn-stack");
    view.header = document.createElement("div");
    view.header.className = "pn-stack-header";
    view.back = document.createElement("button");
    view.back.type = "button";
    view.back.className = "pn-stack-back";
    view.back.addEventListener("click", () => this.goBack(view));
    view.left = document.createElement("div");
    view.left.className = "pn-stack-slot pn-stack-left";
    view.titleEl = document.createElement("span");
    view.titleEl.className = "pn-stack-title";
    view.right = document.createElement("div");
    view.right.className = "pn-stack-slot pn-stack-right";
    const leading = document.createElement("div");
    leading.className = "pn-stack-leading";
    leading.append(view.back, view.left);
    view.header.append(leading, view.titleEl, view.right);
    view.body = document.createElement("div");
    view.body.className = "pn-stack-body";
    view.el.append(view.header, view.body);
    view.topTag = null;
  }
  container(view) {
    return view.body;
  }
  /** Each screen lays out in the stack's bounds below the navigation bar its own options draw. */
  reportContainers(view, report) {
    for (const child of view.children) {
      if (!child.props._pn_header_slot) report(child.tag, view.el, stackHeaderHeight(child.props));
    }
  }
  observed(view) {
    return [view.el];
  }
  goBack(view) {
    if (view.children.length > 1 && view.hasEvent("on_native_back")) view.ctx.emit(view.tag, "on_native_back", [1]);
  }
  command(view, name) {
    // A vetoed back never left the DOM stack in the preview; just redraw.
    if (name === "restore_stack") this.refreshHeader(view);
    return null;
  }
  /** Draw the navigation bar for the top screen and move its header slots into it. */
  refreshHeader(view) {
    const children = view.children;
    const top = children[children.length - 1] || null;
    const o = top?.props || {};
    const height = top ? stackHeaderHeight(o) : 0;
    const scheme = view.ctx.scheme();
    view.header.style.display = height ? "" : "none";
    view.header.style.height = px(height);
    view.header.classList.toggle("pn-stack-large", !!o.header_large_title);
    view.body.style.top = px(height);
    view.titleEl.textContent = o.title == null ? "" : String(o.title);
    const previous = children[children.length - 2];
    const canGoBack = !!previous && o.header_back_visible !== false;
    view.back.style.display = canGoBack ? "" : "none";
    // UIKit labels the back button with the previous screen's title when it
    // fits, and falls back to "Back"; an explicit `header_back_title` wins.
    const explicit = previous?.props.header_back_title;
    const previousTitle = previous?.props.title == null ? "" : String(previous.props.title);
    view.backLabels = explicit != null && explicit !== "" ? [String(explicit), "Back", ""]
      : previousTitle && previousTitle.length <= 12 ? [previousTitle, "Back", ""] : ["Back", ""];
    this.fitBackLabel(view);
    const tint = parseColor(o.header_tint_color, scheme);
    view.back.style.color = tint ?? "";
    const bar = o.header_style && typeof o.header_style === "object" ? o.header_style : {};
    view.header.style.background = parseColor(bar.background_color, scheme) ?? "";
    const titleStyle = o.header_title_style && typeof o.header_title_style === "object" ? o.header_title_style : {};
    view.titleEl.style.color = parseColor(titleStyle.color, scheme) ?? "";
    view.titleEl.style.fontSize = titleStyle.font_size != null ? px(Number(titleStyle.font_size)) : "";
    view.titleEl.style.fontWeight = titleStyle.bold === false ? "400"
      : titleStyle.font_weight != null ? String(titleStyle.font_weight) : titleStyle.bold ? "700" : "";
    for (const child of children) {
      for (const slot of child.children) {
        const side = slot.props._pn_header_slot;
        if (!side) continue;
        if (child === top) (side === "left" ? view.left : view.right).appendChild(slot.el);
        else if (slot.el.parentNode !== child.el) child.el.appendChild(slot.el);
      }
    }
  }
  /**
   * Like UINavigationBar, shorten the back button when it would run into the
   * title: the previous screen's title, then "Back", then the chevron alone.
   */
  fitBackLabel(view) {
    const labels = view.backLabels || ["Back"];
    const room = () => {
      const header = view.header.clientWidth;
      if (!header) return true; // not laid out yet; the next frame refits
      const side = (header - view.titleEl.offsetWidth) / 2 - 12;
      return view.back.scrollWidth <= side;
    };
    for (const label of labels) {
      view.back.textContent = label;
      view.back.classList.toggle("pn-stack-back-chevron", !label);
      if (!label || room()) break;
    }
    view.back.setAttribute("aria-label", labels[0] || "Back");
  }
  /**
   * Show the top screen (and any screens a `transparent_modal` top lets
   * through); hide the rest, except a screen a push is still sliding over.
   */
  syncVisibility(view) {
    const children = view.children;
    const visible = new Set();
    for (let index = children.length - 1; index >= 0; index--) {
      visible.add(children[index]);
      if (children[index].props.presentation !== "transparent_modal") break;
    }
    for (const child of children) {
      child.el.classList.add("pn-stack-screen");
      child.el.classList.toggle("pn-screen-transparent", child.props.presentation === "transparent_modal");
      if (child !== view.covered) child.el.style.display = visible.has(child) ? "" : "none";
    }
  }
  childrenChanged(view) {
    const children = view.children;
    const top = children[children.length - 1] || null;
    const previous = view.topTag;
    view.topTag = top ? top.tag : null;
    const changed = !!top && previous != null && previous !== top.tag && top.el.isConnected;
    const known = view.seen || (view.seen = new Set());
    const pushed = changed && !known.has(top.tag);
    // Every screen in the stack now is "known": its reappearance after a pop
    // is a reveal, not a push. (A root stack never gets a `frame` call.)
    for (const child of children) known.add(child.tag);
    // The screen a push covers stays on stage until the new one has slid over it.
    const covered = pushed ? children.find((child) => child.tag === previous && child !== top) : null;
    if (covered) {
      view.covered?.el.classList.remove("pn-under");
      view.covered = covered;
    }
    this.syncVisibility(view);
    this.refreshHeader(view);
    view.ctx.nativeStackChanged?.();
    const reveal = view.revealFrom;
    view.revealFrom = null;
    if (pushed) this.enter(view, top, covered);
    else if (changed && reveal === "pn-screen-right") this.reveal(top);
  }
  /** Play a push: the new screen slides (or fades) in and a card push nudges the covered one aside. */
  enter(view, child, covered) {
    const cls = screenTransition(child.props);
    const settle = () => {
      if (!covered || view.covered !== covered) return;
      view.covered = null;
      // Hide the covered screen, unless a quick pop already made it the top again.
      this.syncVisibility(view);
      covered.el.classList.remove("pn-under");
    };
    if (!cls) {
      settle();
      return;
    }
    const el = child.el;
    placeOffStage(el, cls);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      el.classList.remove(cls);
      if (covered && cls === "pn-screen-right") covered.el.classList.add("pn-under");
    }));
    setTimeout(settle, SCREEN_TRANSITION_MS + 40);
  }
  /** Play the second half of a card pop: the revealed screen slides back from beneath. */
  reveal(child) {
    const el = child.el;
    placeOffStage(el, "pn-under");
    requestAnimationFrame(() => el.classList.remove("pn-under"));
  }
  /** A child is leaving (pop): animate a snapshot of it out over the revealed screen. */
  childWillDetach(view, child) {
    view.seen?.delete(child.tag);
    const cls = screenTransition(child.props);
    if (!cls || child !== view.children[view.children.length - 1] || !child.el.isConnected) return;
    const ghost = child.el.cloneNode(true);
    ghost.classList.add("pn-screen-ghost");
    ghost.style.pointerEvents = "none";
    ghost.removeAttribute("data-pn-tag");
    view.body.appendChild(ghost);
    view.revealFrom = cls;
    requestAnimationFrame(() => ghost.classList.add(cls));
    setTimeout(() => ghost.remove(), SCREEN_TRANSITION_MS + 40);
  }
  frame(view, x, y, w, h) {
    super.frame(view, x, y, w, h);
    if (view.back.style.display !== "none") this.fitBackLabel(view);
  }
  destroy(view) {
    view.ctx.nativeStackChanged?.();
  }
}

/** A native-stack screen; option changes redraw the stack's navigation bar. */
class ScreenManager extends ViewManager {
  update(view, changed) {
    super.update(view, changed);
    if (view.parent?.type === "ScreenStack") view.parent.manager.refreshHeader(view.parent);
  }
  childrenChanged(view) {
    if (view.parent?.type === "ScreenStack") view.parent.manager.refreshHeader(view.parent);
  }
}


/**
 * A component the preview has no widget for (a plugin's native view): a
 * labeled box that the core sizes like the platform would, so the layout
 * around it stays truthful.
 */
class PlaceholderManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-placeholder";
    el.textContent = view.type;
    el.title = `${view.type} has no browser preview implementation`;
    view.el = el;
    this.update(view, props);
  }
  measure(view, maxW) {
    return [isFiniteConstraint(maxW) ? Math.min(maxW, 160) : 160, 44];
  }
}

const MANAGERS = {
  View: ViewManager,
  Column: ViewManager,
  Row: ViewManager,
  SafeAreaView: ViewManager,
  KeyboardAvoidingView: ViewManager,
  Spacer: SpacerManager,
  Text: TextManager,
  Button: ButtonManager,
  TextInput: TextInputManager,
  Image: ImageManager,
  Svg: SvgManager,
  LinearGradient: LinearGradientManager,
  BlurView: BlurViewManager,
  Switch: SwitchManager,
  Slider: SliderManager,
  ActivityIndicator: ActivityIndicatorManager,
  ProgressBar: ProgressBarManager,
  ScrollView: ScrollViewManager,
  Pressable: PressableManager,
  Checkbox: CheckboxManager,
  SegmentedControl: SegmentedControlManager,
  Picker: PickerManager,
  DatePicker: DatePickerManager,
  TabBar: TabBarManager,
  Modal: ModalManager,
  Portal: PortalManager,
  StatusBar: StatusBarManager,
  WebView: WebViewManager,
  VirtualList: VirtualListManager,
  Screen: ScreenManager,
  ScreenStack: ScreenStackManager,
};

// ---------------------------------------------------------------------------
// Animated writes (PNAnimator equivalent)
// ---------------------------------------------------------------------------

const ANIM_TRANSFORM = new Set(["translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate", "rotate_x", "rotate_y"]);

/** An animated angle in degrees (`"45deg"`, `"0.5rad"`, or a bare number of degrees). */
function degrees(value) {
  const n = typeof value === "string" ? parseFloat(value) : Number(value);
  if (!Number.isFinite(n)) return 0;
  return typeof value === "string" && value.endsWith("rad") ? (n * 180) / Math.PI : n;
}

// ---------------------------------------------------------------------------
// Gestures: pointer streams go to the core's gesture engine
// ---------------------------------------------------------------------------

function installGestureSource(view) {
  if (view.gestureInstalled) return;
  view.gestureInstalled = true;
  const el = view.el;
  const wired = () => Array.isArray(view.props.gestures) && view.props.gestures.length > 0;
  el.addEventListener("pointerdown", (event) => {
    if (!wired()) return;
    try {
      el.setPointerCapture(event.pointerId);
    } catch (err) {
      /* ignore */
    }
    view.gestureActive = true;
    view.ctx.pointer(view, POINTER_DOWN, event);
  });
  el.addEventListener("pointermove", (event) => {
    if (view.gestureActive) view.ctx.pointer(view, POINTER_MOVE, event);
  });
  el.addEventListener("pointerup", (event) => {
    if (!view.gestureActive) return;
    view.gestureActive = false;
    view.ctx.pointer(view, POINTER_UP, event);
  });
  el.addEventListener("pointercancel", (event) => {
    if (!view.gestureActive) return;
    view.gestureActive = false;
    view.ctx.pointer(view, POINTER_CANCEL, event);
  });
}

// ---------------------------------------------------------------------------
// The renderer
// ---------------------------------------------------------------------------

export class Renderer {
  /**
   * @param ctx {{
   *   scheme(), overlays(), bottomInset(), frameWidth(), pointInFrame(event),
   *   pointInWindow(event), windowOrigin(el), statusBar(opts), nativeStackChanged()
   * }}
   */
  constructor(ctx) {
    this.ctx = {...ctx};
    this.host = null;
    this.surface = 1;
    this.ctx.emit = (tag, name, args) => {
      const view = this.views.get(tag);
      const edit = name === "on_change" && view?.type === "TextInput" ? (view.editRevision = (view.editRevision || 0) + 1) : 0;
      this.host?.event(this.surface, tag, name, args, edit);
    };
    this.ctx.pointer = (view, phase, event) => {
      if (!this.host) return;
      const local = this.ctx.pointInFrame(event);
      const window = this.ctx.pointInWindow ? this.ctx.pointInWindow(event) : { x: event.clientX, y: event.clientY };
      this.host.pointer(this.surface, view.tag, [{
        phase, pointer: event.pointerId || 0, x: local.x, y: local.y, windowX: window.x, windowY: window.y,
        time: (event.timeStamp || performance.now()) / 1000,
      }]);
    };
    this.ctx.invalidate = (tag) => this.host?.core.invalidate(this.surface, tag);
    this.ctx.reportIntrinsic = (tag, width, height) => this.host?.core.reportIntrinsic(this.surface, tag, width, height);
    this.ctx.list = () => this.host?.core;
    this.ctx.surface = () => this.surface;
    this.ctx.viewFor = (tag) => this.views.get(tag) || null;
    this.views = new Map();
    this.managers = {};
    this.placeholder = new PlaceholderManager();
    this.dirtyContainers = new Set();
    this.containers = new Set();
    this.reported = new Map();
    this.prototypes = new Map();
    this.resizes = typeof ResizeObserver === "function" ? new ResizeObserver(() => this.reportContainers()) : null;
    for (const [name, Manager] of Object.entries(MANAGERS)) this.managers[name] = new Manager();
  }

  /** Connect the core's platform host (`core/mount.js`). */
  attach(host) {
    this.host = host;
  }

  /** Destroy every view (a `reset` op, or the page leaving Python). */
  reset() {
    for (const view of this.views.values()) {
      try {
        view.manager.destroy(view);
      } catch (err) {
        /* ignore */
      }
      this.host?.forgetGestures(view.tag);
      view.el.remove();
    }
    this.views.clear();
    this.dirtyContainers.clear();
    this.containers.clear();
    this.reported.clear();
    for (const tag of [...this.prototypes.keys()]) this.forgetPrototype(tag);
    this.resizes?.disconnect();
  }

  // -- mount transactions --------------------------------------------------

  /** Apply one decoded transaction; the first failing op fails it (and the surface). */
  applyTransaction(transaction) {
    this.surface = transaction.surface;
    try {
      for (const op of transaction.ops) this.applyOp(op);
      for (const view of this.dirtyContainers) if (this.views.has(view.tag)) view.manager.childrenChanged(view);
    } finally {
      this.dirtyContainers.clear();
    }
    this.reportContainers();
  }

  applyOp(op) {
    switch (op.kind) {
      case "reset": this.reset(); return;
      case "create": this.create(op.tag, op.component, op.props); return;
      case "update": this.update(this.require(op.tag, "update"), op.props, op.removed, op.recreate); return;
      case "insert": this.insert(this.require(op.parent, "insert"), this.require(op.tag, "insert"), op.index); return;
      case "delete": this.destroyView(this.require(op.tag, "delete")); return;
      case "frame": this.frame(this.require(op.tag, "frame"), op.frame); return;
      case "command": this.command(op); return;
      default: throw new Error(`unknown mount op ${op.kind}`);
    }
  }

  require(tag, what) {
    const view = this.views.get(tag);
    if (!view) throw new Error(`${what}: unknown tag ${tag}`);
    return view;
  }

  /** A view record and its element, before it joins the tree. */
  build(tag, type, props, ctx = this.ctx) {
    const manager = this.managers[type] || this.placeholder;
    const view = { tag, type, props: { ...(props || {}) }, manager, ctx, children: [], parent: null, frame: null, el: null, hasEvent: null };
    view.hasEvent = (name) => Array.isArray(view.props._pn_events) && view.props._pn_events.includes(name);
    manager.create(view, view.props);
    return view;
  }

  create(tag, type, props) {
    if (this.views.has(tag)) throw new Error(`create: tag ${tag} already exists`);
    const view = this.build(tag, type, props);
    view.el.dataset.pnTag = String(tag);
    view.el.dataset.pnType = type;
    if (Array.isArray(view.props.gestures) && view.props.gestures.length) installGestureSource(view);
    this.views.set(tag, view);
    this.watchContainer(view);
  }

  update(view, changed, removed, recreate) {
    Object.assign(view.props, changed);
    for (const key of removed) delete view.props[key];
    if (recreate) this.recreate(view, changed);
    else view.manager.update(view, changed);
    if (Array.isArray(view.props.gestures) && view.props.gestures.length) installGestureSource(view);
  }

  /** Rebuild a widget in place (a creation-only prop changed), keeping its children, frame, focus, and text selection. */
  recreate(view, changed) {
    const old = view.el, focused = document.activeElement === old;
    const selection = [old.selectionStart, old.selectionEnd];
    const scroll = [old.scrollLeft, old.scrollTop];
    if (view.type === "TextInput" && (!("value" in changed) || (changed._pn_edit_revision || 0) < (view.editRevision || 0))) view.props.value = old.value;
    const edited = view.editRevision || 0;
    view.editRevision = 0;
    view.manager.destroy(view);
    view.gestureInstalled = false;
    this.unwatchContainer(view);
    view.manager.create(view, view.props);
    view.editRevision = edited;
    old.replaceWith(view.el);
    view.el.dataset.pnTag = String(view.tag); view.el.dataset.pnType = view.type;
    const container = view.manager.container(view);
    for (const child of view.children) container.appendChild(child.el);
    view.manager.childrenChanged(view);
    if (view.frame) view.manager.frame(view, view.frame.x, view.frame.y, view.frame.w, view.frame.h);
    view.el.scrollLeft = scroll[0]; view.el.scrollTop = scroll[1];
    if (focused) view.el.focus();
    if (selection[0] != null && view.el.setSelectionRange) view.el.setSelectionRange(...selection);
    this.watchContainer(view);
  }

  /** Move-aware: a child under another parent leaves it first. */
  insert(parent, child, index) {
    if (child.parent && child.parent !== parent) {
      const idx = child.parent.children.indexOf(child);
      if (idx >= 0) child.parent.children.splice(idx, 1);
      this.dirtyContainers.add(child.parent);
    } else if (child.parent === parent) {
      const idx = parent.children.indexOf(child);
      if (idx >= 0) parent.children.splice(idx, 1);
    }
    const at = Math.max(0, Math.min(index, parent.children.length));
    parent.children.splice(at, 0, child);
    child.parent = parent;
    const container = parent.manager.container(parent);
    const before = parent.children[at + 1] ? parent.children[at + 1].el : null;
    if (before && before.parentNode === container) container.insertBefore(child.el, before);
    else container.appendChild(child.el);
    applyPointerInheritance(child, parent);
    this.dirtyContainers.add(parent);
  }

  /** Delete one view; it also leaves its parent, and children still under it (moved later) leave it. */
  destroyView(view) {
    if (view.parent && view.parent.manager.childWillDetach) view.parent.manager.childWillDetach(view.parent, view);
    for (const child of view.children) {
      child.parent = null;
      child.el.remove();
    }
    view.children = [];
    if (view.parent) {
      const idx = view.parent.children.indexOf(view);
      if (idx >= 0) view.parent.children.splice(idx, 1);
      this.dirtyContainers.add(view.parent);
      view.parent = null;
    }
    try {
      view.manager.destroy(view);
    } catch (err) {
      /* ignore */
    }
    view.el.remove();
    this.views.delete(view.tag);
    this.dirtyContainers.delete(view);
    this.forgetPrototype(view.tag);
    this.reported.delete(view.tag);
    this.unwatchContainer(view);
    this.host?.forgetGestures(view.tag);
  }

  /** A frame relative to the mounted parent (flattened ancestors already folded in). */
  frame(view, [x, y, w, h]) {
    view.frame = { x, y, w, h };
    view.manager.frame(view, x, y, w, h);
    if (view.parent) this.dirtyContainers.add(view.parent);
    if (view.children.length) this.dirtyContainers.add(view);
  }

  command(op) {
    const view = this.views.get(op.tag);
    if (!view) {
      this.host?.commandResult(op.call_id, false, null, `unknown view ${op.tag}`);
      return;
    }
    let value;
    try {
      value = view.manager.command(view, op.name, op.arguments || {});
    } catch (error) {
      this.host?.commandResult(op.call_id, false, null, String(error?.message || error));
      return;
    }
    this.host?.commandResult(op.call_id, true, value === undefined ? null : value);
  }

  // -- container sizes -----------------------------------------------------

  watchContainer(view) {
    if (!view.manager.reportContainers) return;
    this.containers.add(view);
    for (const el of view.manager.observed?.(view) || []) this.resizes?.observe(el);
  }

  unwatchContainer(view) {
    if (!this.containers.delete(view)) return;
    for (const el of view.manager.observed?.(view) || []) this.resizes?.unobserve(el);
  }

  /**
   * Report the size (and window origin) of every container a detached root
   * lays out in: each stack screen, a presented modal's sheet, and the portal
   * layer. The core relayouts those roots when a size changes.
   */
  reportContainers() {
    if (!this.host) return;
    for (const view of this.containers) {
      if (!this.views.has(view.tag)) continue;
      view.manager.reportContainers(view, (tag, el, inset = 0) => {
        const width = el.clientWidth, height = el.clientHeight - inset;
        if (!el.isConnected || width <= 0 || height <= 0) return;
        const origin = this.ctx.windowOrigin ? this.ctx.windowOrigin(el) : { x: 0, y: 0 };
        const key = `${origin.x},${origin.y + inset},${width},${height}`;
        if (this.reported.get(tag) === key) return;
        this.reported.set(tag, key);
        this.host.core.reportContainer(this.surface, tag, origin.x, origin.y + inset, width, height);
      });
    }
  }

  // -- measurement (called by the core during a commit or a layout) ----------

  /**
   * Measure a leaf the way the platforms do: a prototype element built from
   * the props, measured off-screen with the fonts and styles it renders
   * with. `text` and `intrinsic` share this path; `native` (a plugin's
   * measurement) has no browser implementation, so it measures the
   * placeholder.
   */
  measure({ tag, component, props, width, widthMode, height, heightMode }) {
    const maxW = widthMode ? width : INF;
    const maxH = heightMode ? height : INF;
    // A text input sizes to what the user typed, which Python may not know yet.
    if (component === "TextInput" && !("value" in props)) {
      const live = this.views.get(tag);
      if (live?.el && "value" in live.el) props.value = live.el.value;
    }
    const proto = this.prototype(tag, component, props);
    if (!measureRoot) measureRoot = document.getElementById("pn-measure") || document.body;
    measureRoot.appendChild(proto.el);
    try {
      return proto.manager.measure(proto, maxW, maxH);
    } finally {
      proto.el.remove();
    }
  }

  /** A text leaf's first baseline, from its last measured prototype. */
  baseline(tag, width, height) {
    const proto = this.prototypes.get(tag)?.view;
    return proto?.manager.baseline ? proto.manager.baseline(proto, width, height) : height;
  }

  /** The prototype for `tag`, rebuilt when its props change; its events go nowhere. */
  prototype(tag, component, props) {
    const key = `${component}:${JSON.stringify(props)}`;
    const cached = this.prototypes.get(tag);
    if (cached && cached.key === key) return cached.view;
    this.forgetPrototype(tag);
    const ctx = { ...this.ctx, emit() {}, pointer() {}, invalidate() {}, reportIntrinsic() {} };
    const view = this.build(-tag, component, props, ctx);
    this.prototypes.set(tag, { key, view });
    return view;
  }

  forgetPrototype(tag) {
    const cached = this.prototypes.get(tag);
    if (!cached) return;
    this.prototypes.delete(tag);
    try {
      cached.view.manager.destroy(cached.view);
    } catch (err) {
      /* ignore */
    }
  }

  // -- animated writes ------------------------------------------------------

  /** Apply one animated prop write (`pn_core_take_writes`). */
  applyAnimated(tag, prop, value) {
    const view = this.views.get(tag);
    if (!view || value == null) return;
    if (ANIM_TRANSFORM.has(prop)) {
      view.animTransform = view.animTransform || {};
      view.animTransform[prop] = prop.startsWith("rotate") ? degrees(value) : Number(value) || 0;
      composeTransform(view);
    } else if (prop === "opacity") {
      view.el.style.opacity = String(value);
    } else if (prop === "background_color") {
      view.el.style.backgroundColor = parseColor(value, this.ctx.scheme()) ?? "";
    } else if (prop === "color") {
      view.el.style.color = parseColor(value, this.ctx.scheme()) ?? "";
    }
    view.animValues = view.animValues || {};
    view.animValues[prop] = value;
  }

  /** Re-apply every color-bearing prop after a light/dark switch. */
  refreshColors() {
    for (const view of this.views.values()) {
      const changed = {};
      for (const key of Object.keys(view.props)) {
        if (isColorProp(key) || key === "spans" || key === "refresh_control") changed[key] = view.props[key];
      }
      if (Object.keys(changed).length) view.manager.update(view, changed);
    }
  }
}
