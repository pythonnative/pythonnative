// The DOM "native runtime" for the browser preview.
//
// This module plays the role PythonNativeKit (Swift) and the pythonnative
// Gradle module (Kotlin) play on device: it applies transactions
// (create/update/insert/destroy/frame ops), answers `measure`,
// `command`, and `animate`, and raises `callback("event", ...)` for
// user interaction. Layout is not done here; the Python flexbox engine
// positions every view and sends frames in points, which are CSS px
// inside the phone frame.
//
// Component managers mirror the Swift `PN*Manager` classes prop for
// prop (see docs/concepts/bridge.md and the iOS sources); where the
// browser cannot honor a prop it is accepted and ignored, never thrown.

import { color as parseColor, isColorProp } from "./colors.js";

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
  "accessible",
  "accessibility_label",
  "accessibility_hint",
  "accessibility_role",
  "accessibility_state",
  "test_id",
]);

function offsetOf(value) {
  if (Array.isArray(value)) return { x: Number(value[0]) || 0, y: Number(value[1]) || 0 };
  if (value && typeof value === "object") return { x: Number(value.width) || 0, y: Number(value.height) || 0 };
  return { x: 0, y: 0 };
}

function transformToCSS(value) {
  if (value == null) return "";
  const ops = Array.isArray(value) ? value : [value];
  const parts = [];
  for (const op of ops) {
    if (!op || typeof op !== "object") continue;
    for (const [key, raw] of Object.entries(op)) {
      const n = typeof raw === "string" ? parseFloat(raw) : Number(raw);
      if (!Number.isFinite(n)) return "";
      switch (key) {
        case "rotate": {
          const rad = typeof raw === "string" && raw.endsWith("rad");
          parts.push(`rotate(${rad ? n + "rad" : n + "deg"})`);
          break;
        }
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
          parts.push(`skewX(${n}deg)`);
          break;
        case "skew_y":
          parts.push(`skewY(${n}deg)`);
          break;
        default:
          break;
      }
    }
  }
  return parts.join(" ");
}

/** Style keys shared by containers and leaves. `leaf` skips the container-only ones. */
export function applyStyle(view, props, changed, scheme, { leaf = false } = {}) {
  const el = view.el;
  const s = el.style;
  const c = (v) => parseColor(v, scheme);
  const has = (k) => k in changed;

  if (!leaf) {
    if (has("background_color")) s.backgroundColor = c(props.background_color) ?? "";
    if (has("overflow")) s.overflow = props.overflow === "hidden" ? "hidden" : "";
    if (has("display")) s.display = props.display === "none" ? "none" : "";
    if (has("z_index")) s.zIndex = props.z_index == null ? "" : String(props.z_index);
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
    const sides = ["top", "right", "bottom", "left"];
    for (const side of sides) {
      const width = props[`border_${side}_width`];
      const sideColor = c(props[`border_${side}_color`]);
      const w = width != null ? Number(width) || 0 : uniform;
      const Side = side[0].toUpperCase() + side.slice(1);
      s[`border${Side}`] = w > 0 ? `${px(w)} solid ${sideColor ?? uniformColor}` : "";
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

class TextManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-text";
    view.el = el;
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    if ("text" in changed || "spans" in changed) this.render(view);
    applyTextStyle(el, props, changed, scheme);
    if ("max_lines" in changed || "number_of_lines" in changed) {
      const n = Number(props.max_lines ?? props.number_of_lines) || 0;
      el.classList.toggle("pn-clamp", n > 1);
      el.classList.toggle("pn-clamp-1", n === 1);
      el.style.webkitLineClamp = n > 1 ? String(n) : "";
      view.maxLines = n;
    }
    if ("selectable" in changed) el.classList.toggle("pn-selectable", !!props.selectable);
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
  }
  render(view) {
    const el = view.el;
    const props = view.props;
    el.textContent = "";
    if (Array.isArray(props.spans) && props.spans.length) {
      const scheme = view.ctx.scheme();
      for (const span of props.spans) {
        if (!span || typeof span !== "object") continue;
        const node = document.createElement("span");
        node.textContent = span.text == null ? "" : String(span.text);
        applyTextStyle(node, span, span, scheme);
        el.appendChild(node);
      }
      return;
    }
    el.textContent = props.text == null ? "" : String(props.text);
  }
  measure(view, maxW, maxH) {
    const key = `${maxW}|${maxH}`;
    if (view.measureCache && view.measureCache.key === key) return view.measureCache.size;
    let size = measureElement(view.el, maxW, maxH, { block: true });
    if (view.maxLines > 0) {
      const lh = parseFloat(getComputedStyle(view.el).lineHeight) || Number(view.props.font_size || 17) * 1.25;
      size = [size[0], Math.min(size[1], Math.ceil(lh * view.maxLines * 100) / 100)];
    }
    view.measureCache = { key, size };
    return size;
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
    if ("enabled" in changed) el.disabled = props.enabled === false;
    applyStyle(view, props, changed, scheme, { leaf: true });
    view.measureCache = null;
  }
  measure(view, maxW, maxH) {
    const [w, h] = measureElement(view.el, maxW, maxH);
    return [Math.max(44, Math.min(w + 24, isFiniteConstraint(maxW) ? maxW : Infinity)), Math.max(32, h + 12)];
  }
}

const KEYBOARD_TYPES = {
  ascii: "text",
  numbers_and_punctuation: "text",
  url: "url",
  number_pad: "tel",
  numeric: "text",
  phone_pad: "tel",
  email_address: "email",
  email: "email",
  decimal_pad: "text",
  decimal: "text",
  web_search: "search",
};

class TextInputManager extends ViewManager {
  create(view, props) {
    const multiline = !!props.multiline;
    const el = document.createElement(multiline ? "textarea" : "input");
    el.className = "pn-view pn-input";
    if (!multiline) el.type = "text";
    view.el = el;
    view.suppressEcho = false;
    el.addEventListener("input", () => {
      const props = view.props;
      if (props.max_length != null && el.value.length > Number(props.max_length)) {
        el.value = el.value.slice(0, Number(props.max_length));
      }
      view.ctx.emit(view.tag, "on_change", [el.value]);
    });
    el.addEventListener("focus", () => view.ctx.emit(view.tag, "on_focus", []));
    el.addEventListener("blur", () => view.ctx.emit(view.tag, "on_blur", []));
    if (!multiline) {
      el.addEventListener("keydown", (event) => {
        if (event.key === "Enter") view.ctx.emit(view.tag, "on_submit", [el.value]);
      });
    }
    document.addEventListener("selectionchange", () => {
      if (document.activeElement !== el || !view.hasEvent("on_selection_change")) return;
      view.ctx.emit(view.tag, "on_selection_change", [{ start: el.selectionStart || 0, end: el.selectionEnd || 0 }]);
    });
    this.update(view, props);
    if (props.auto_focus) setTimeout(() => el.focus(), 0);
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("value") && props.value != null && el.value !== String(props.value)) el.value = String(props.value);
    if (has("placeholder")) el.placeholder = props.placeholder == null ? "" : String(props.placeholder);
    if (has("placeholder_color")) el.style.setProperty("--pn-placeholder", parseColor(props.placeholder_color, scheme) ?? "");
    if (has("font_size")) el.style.fontSize = props.font_size != null ? px(Number(props.font_size)) : "";
    if (has("color")) el.style.color = parseColor(props.color, scheme) ?? "";
    if (has("background_color")) el.style.backgroundColor = parseColor(props.background_color, scheme) ?? "";
    if (has("secure") && el.tagName === "INPUT") el.type = props.secure ? "password" : KEYBOARD_TYPES[props.keyboard_type] || "text";
    if (has("keyboard_type") && el.tagName === "INPUT" && !props.secure) el.type = KEYBOARD_TYPES[props.keyboard_type] || "text";
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
      const [, h] = measureElement(view.el, maxW, INF, { block: true });
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
        return null;
      case "get_value":
        return el.value;
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
    img.addEventListener("load", () => {
      view.natural = [img.naturalWidth, img.naturalHeight];
      view.measureCache = null;
      view.ctx.emit(view.tag, "on_load", [{ width: img.naturalWidth, height: img.naturalHeight }]);
    });
    img.addEventListener("error", () => view.ctx.emit(view.tag, "on_error", [`failed to load ${img.src}`]));
    this.update(view, props);
  }
  update(view, changed) {
    const props = view.props;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("source")) {
      const src = imageSource(props.source);
      view.natural = null;
      if (src) view.img.src = src;
      else view.img.removeAttribute("src");
      view.tint.style.maskImage = view.tint.style.webkitMaskImage = src ? `url("${src}")` : "";
    }
    if (has("scale_type") || has("resize_mode")) {
      const mode = props.scale_type ?? props.resize_mode;
      view.img.style.objectFit = mode === "cover" || mode === "repeat" ? "cover" : mode === "stretch" ? "fill" : mode === "center" ? "none" : "contain";
    }
    if (has("placeholder_color")) view.el.style.backgroundColor = parseColor(props.placeholder_color, scheme) ?? "";
    if (has("tint_color") || has("tint")) {
      const tint = parseColor(props.tint_color ?? props.tint, scheme);
      view.tint.style.display = tint ? "" : "none";
      view.tint.style.backgroundColor = tint ?? "";
      view.img.style.visibility = tint ? "hidden" : "";
    }
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  measure(view, maxW, maxH) {
    if (!view.natural) return [0, 0];
    let [w, h] = view.natural;
    if (isFiniteConstraint(maxW) && w > maxW) {
      h = (h * maxW) / w;
      w = maxW;
    }
    if (isFiniteConstraint(maxH) && h > maxH) {
      w = (w * maxH) / h;
      h = maxH;
    }
    return [w, h];
  }
}

function imageSource(source) {
  if (source == null) return "";
  if (typeof source === "object") source = source.uri ?? source.url ?? source.src ?? "";
  const text = String(source);
  if (!text) return "";
  if (/^(https?:|data:|blob:|\/)/.test(text)) return text;
  if (text.startsWith("file://")) return `/file/${encodeURI(text.slice("file://".length).replace(/^\/+/, ""))}`;
  // Bundle-relative name: serve it out of the project through the dev server.
  return `/file/${encodeURI(text.replace(/^\.?\//, ""))}`;
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
      if (view.props.enabled === false) return;
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
    if ("enabled" in changed) el.classList.toggle("pn-disabled", props.enabled === false);
    applyStyle(view, props, changed, scheme, { leaf: true });
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
    el.addEventListener("input", () => view.ctx.emit(view.tag, "on_change", [Number(el.value)]));
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
      el.style.accentColor = parseColor(props.minimum_track_color ?? props.tint_color, scheme) ?? "";
    }
    if ("maximum_track_color" in changed) el.style.setProperty("--pn-track", parseColor(props.maximum_track_color, scheme) ?? "");
    if ("thumb_color" in changed) el.style.setProperty("--pn-thumb", parseColor(props.thumb_color, scheme) ?? "");
    if ("enabled" in changed) el.disabled = props.enabled === false;
    applyStyle(view, props, changed, scheme, { leaf: true });
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
    applyStyle(view, props, changed, scheme, { leaf: true });
  }
  measure(view, maxW) {
    if (view.indeterminate) return [20, 20];
    return [isFiniteConstraint(maxW) ? maxW : 100, 4];
  }
}

function scrollPayload(el, horizontal) {
  const contentWidth = el.scrollWidth;
  const contentHeight = el.scrollHeight;
  return {
    x: el.scrollLeft,
    y: el.scrollTop,
    extent: horizontal ? el.clientWidth : el.clientHeight,
    range: horizontal ? contentWidth : contentHeight,
    content_width: contentWidth,
    content_height: contentHeight,
    width: el.clientWidth,
    height: el.clientHeight,
  };
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
    view.dragging = false;
    el.addEventListener(
      "scroll",
      () => {
        const props = view.props;
        const horizontal = !!props.horizontal;
        if (!view.dragging) {
          view.dragging = true;
          if (view.hasEvent("on_scroll_begin_drag")) view.ctx.emit(view.tag, "on_scroll_begin_drag", [scrollPayload(el, horizontal)]);
        }
        const throttle = Number(props.scroll_event_throttle) || 0;
        const now = performance.now();
        if (throttle <= 0 || now - view.lastScrollEmit >= throttle) {
          view.lastScrollEmit = now;
          view.ctx.emit(view.tag, "on_scroll", [scrollPayload(el, horizontal)]);
        }
        clearTimeout(view.scrollIdleTimer);
        view.scrollIdleTimer = setTimeout(() => {
          view.dragging = false;
          const payload = scrollPayload(el, horizontal);
          view.ctx.emit(view.tag, "on_scroll", [payload]);
          if (view.hasEvent("on_scroll_end_drag")) view.ctx.emit(view.tag, "on_scroll_end_drag", [payload]);
          if (view.hasEvent("on_momentum_scroll_end")) view.ctx.emit(view.tag, "on_momentum_scroll_end", [payload]);
        }, 120);
      },
      { passive: true },
    );
    this.update(view, props);
  }
  container(view) {
    return view.content;
  }
  update(view, changed) {
    const props = view.props;
    const el = view.el;
    const scheme = view.ctx.scheme();
    const has = (k) => k in changed;
    if (has("horizontal")) {
      el.style.overflowX = props.horizontal ? "auto" : "hidden";
      el.style.overflowY = props.horizontal ? "hidden" : "auto";
    }
    if (has("shows_scroll_indicator")) el.classList.toggle("pn-no-indicator", props.shows_scroll_indicator === false);
    if (has("paging_enabled")) el.classList.toggle("pn-paging", !!props.paging_enabled);
    if (has("scroll_enabled")) el.classList.toggle("pn-scroll-disabled", props.scroll_enabled === false);
    if (has("content_inset")) {
      const inset = props.content_inset || {};
      view.content.style.padding = `${px(Number(inset.top) || 0)} ${px(Number(inset.right) || 0)} ${px(Number(inset.bottom) || 0)} ${px(Number(inset.left) || 0)}`;
    }
    if (has("refresh_control")) this.updateRefresh(view);
    applyStyle(view, props, changed, scheme);
    if ("overflow" in changed && props.overflow !== "hidden") el.style.overflow = "";
    if (has("horizontal") || has("overflow")) {
      el.style.overflowX = props.horizontal ? "auto" : "hidden";
      el.style.overflowY = props.horizontal ? "hidden" : "auto";
    }
  }
  updateRefresh(view) {
    const rc = view.props.refresh_control;
    if (!rc || typeof rc !== "object") {
      if (view.refresh) view.refresh.remove();
      view.refresh = null;
      return;
    }
    if (!view.refresh) {
      const bar = document.createElement("div");
      bar.className = "pn-refresh";
      const button = document.createElement("button");
      button.className = "pn-button";
      button.textContent = "↻ Refresh";
      button.style.fontSize = "13px";
      button.addEventListener("click", () => view.ctx.emit(view.tag, "on_refresh", []));
      const spinner = document.createElement("div");
      spinner.className = "pn-spinner";
      spinner.style.width = spinner.style.height = "20px";
      bar.appendChild(button);
      bar.appendChild(spinner);
      view.el.insertBefore(bar, view.content);
      view.refresh = bar;
      view.refreshButton = button;
      view.refreshSpinner = spinner;
    }
    const refreshing = !!rc.refreshing;
    view.refreshButton.style.display = refreshing ? "none" : "";
    view.refreshSpinner.style.display = refreshing ? "" : "none";
    const tint = parseColor(rc.tint_color ?? rc.color, view.ctx.scheme());
    if (tint) view.refreshSpinner.style.borderTopColor = tint;
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
    const enabled = () => view.props.enabled !== false && !view.props.disabled;
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
    const disabled = props.enabled === false || !!props.disabled;
    view.el.classList.toggle("pn-disabled", disabled);
    view.el.tabIndex = disabled ? -1 : 0;
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
    if ("segments" in changed || "selected_index" in changed || "enabled" in changed || "tint_color" in changed) {
      el.textContent = "";
      const segments = Array.isArray(props.segments) ? props.segments : [];
      segments.forEach((label, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(label);
        button.disabled = props.enabled === false;
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
    if ("enabled" in changed) el.disabled = props.enabled === false;
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
    const activeIndex = props.active_index != null ? Number(props.active_index) : -1;
    el.style.setProperty("--pn-tab-active", parseColor(props.active_color ?? props.tint_color, scheme) ?? "");
    const inactive = parseColor(props.inactive_color, scheme);
    el.style.paddingBottom = px(view.ctx.bottomInset());
    items.forEach((item, index) => {
      const name = item.name ?? item.title ?? String(index);
      const button = document.createElement("button");
      button.type = "button";
      const active = activeName != null ? name === activeName : index === activeIndex;
      button.classList.toggle("pn-active", active);
      if (!active && inactive) button.style.color = inactive;
      const icon = document.createElement("span");
      icon.className = "pn-tab-icon";
      icon.textContent = tabIcon(item.icon);
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
      button.addEventListener("click", () => {
        view.ctx.emit(view.tag, "on_tab_select", [name]);
        if (view.hasEvent("on_select")) view.ctx.emit(view.tag, "on_select", [index]);
      });
      el.appendChild(button);
    });
    applyStyle(view, props, changed, scheme);
    if ("background_color" in changed && props.background_color == null) el.style.backgroundColor = "";
  }
  measure(view, maxW) {
    return [isFiniteConstraint(maxW) ? maxW : view.ctx.frameWidth(), 49 + view.ctx.bottomInset()];
  }
}

const TAB_ICONS = {
  house: "⌂",
  home: "⌂",
  gear: "⚙",
  settings: "⚙",
  person: "☺",
  profile: "☺",
  star: "★",
  heart: "♥",
  magnifyingglass: "⌕",
  search: "⌕",
  bell: "🔔",
  list: "☰",
  plus: "＋",
  camera: "📷",
  map: "🗺",
  cart: "🛒",
  chat: "💬",
  message: "💬",
};

function tabIcon(icon) {
  if (icon && typeof icon === "object") icon = icon.web ?? icon.ios ?? icon.android ?? "";
  const name = String(icon || "").toLowerCase().replace(/\.fill$/, "").replace(/\.circle$/, "");
  if (!name) return "●";
  for (const [key, glyph] of Object.entries(TAB_ICONS)) {
    if (name.includes(key)) return glyph;
  }
  return "●";
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
    backdrop.addEventListener("click", (event) => {
      if (event.target !== backdrop) return;
      if (view.props.dismiss_on_backdrop === false) return;
      if (view.hasEvent("on_request_close")) view.ctx.emit(view.tag, "on_request_close", []);
    });
    view.el = el;
    view.backdrop = backdrop;
    view.sheet = sheet;
    view.shown = false;
    this.update(view, props);
  }
  container(view) {
    return view.sheet;
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
    const visible = !!props.visible;
    if (visible && !view.shown) {
      view.shown = true;
      view.ctx.overlays().appendChild(view.backdrop);
      view.ctx.emit(view.tag, "on_show", []);
    } else if (!visible && view.shown) {
      view.shown = false;
      view.backdrop.remove();
      view.ctx.emit(view.tag, "on_dismiss", []);
    }
  }
  destroy(view) {
    if (view.shown) view.backdrop.remove();
  }
}

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
    view.frame = frame;
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
      view.frame.removeAttribute("srcdoc");
      view.frame.src = String(props.url);
      if (view.hasEvent("on_load_start")) view.ctx.emit(view.tag, "on_load_start", [String(props.url)]);
    } else if ("html" in changed && props.html != null) {
      const shim =
        "<script>window.webkit={messageHandlers:{pythonnative:{postMessage:function(m){parent.postMessage(m,'*');}}}};</script>";
      view.frame.srcdoc = shim + String(props.html);
    }
    if ("scroll_enabled" in changed) view.frame.style.overflow = props.scroll_enabled === false ? "hidden" : "";
    applyStyle(view, props, changed, view.ctx.scheme(), { leaf: true });
  }
  command(view, name, args) {
    const win = view.frame.contentWindow;
    try {
      switch (name) {
        case "eval_js":
        case "inject_javascript":
          win.eval(String(args.source ?? args.script ?? ""));
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
          view.frame.src = String(args.url || "");
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

class VirtualListManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-vlist";
    const spacer = document.createElement("div");
    spacer.className = "pn-vlist-spacer";
    el.appendChild(spacer);
    view.el = el;
    view.spacer = spacer;
    view.rows = new Map(); // index -> {container, el, key}
    view.freeKeys = [];
    view.nextKey = 1;
    view.offsets = [];
    view.binding = 0;
    el.addEventListener(
      "scroll",
      () => {
        this.refill(view);
        if (view.hasEvent("on_scroll")) view.ctx.emit(view.tag, "on_scroll", [scrollPayload(el, false)]);
        clearTimeout(view.idle);
        view.idle = setTimeout(() => {
          if (view.hasEvent("on_momentum_scroll_end")) view.ctx.emit(view.tag, "on_momentum_scroll_end", [scrollPayload(el, false)]);
        }, 120);
      },
      { passive: true },
    );
    this.update(view, props);
  }
  container(view) {
    return view.spacer;
  }
  update(view, changed) {
    const props = view.props;
    const has = (k) => k in changed;
    if (has("count") || has("row_height") || has("row_heights")) this.layoutRows(view);
    if (has("shows_scroll_indicator")) view.el.classList.toggle("pn-no-indicator", props.shows_scroll_indicator === false);
    if (has("scroll_enabled")) view.el.classList.toggle("pn-scroll-disabled", props.scroll_enabled === false);
    if (has("generation") || has("data_version")) this.reload(view);
    if (has("content_inset")) {
      const inset = props.content_inset || {};
      view.spacer.style.marginTop = px(Number(inset.top) || 0);
      view.spacer.style.marginBottom = px(Number(inset.bottom) || 0);
    }
    applyStyle(view, props, changed, view.ctx.scheme());
    view.el.style.overflow = props.scroll_enabled === false ? "hidden" : "auto";
    this.refill(view);
  }
  layoutRows(view) {
    const props = view.props;
    const count = Math.max(0, Number(props.count) || 0);
    const heights = Array.isArray(props.row_heights) ? props.row_heights : null;
    const rowHeight = Number(props.row_height) || 44;
    const offsets = new Array(count + 1);
    offsets[0] = 0;
    for (let i = 0; i < count; i++) {
      const h = heights && heights[i] != null ? Number(heights[i]) : rowHeight;
      offsets[i + 1] = offsets[i] + h;
    }
    view.offsets = offsets;
    view.spacer.style.height = px(offsets[count]);
    for (const [index, row] of [...view.rows]) {
      if (index >= count) this.unbind(view, index, row);
    }
  }
  frame(view, x, y, w, h) {
    super.frame(view, x, y, w, h);
    this.refill(view);
  }
  reload(view) {
    for (const [index, row] of [...view.rows]) this.unbind(view, index, row);
    this.refill(view);
  }
  visibleRange(view) {
    const offsets = view.offsets;
    const count = offsets.length - 1;
    if (count <= 0) return [0, 0];
    const top = view.el.scrollTop - view.el.clientHeight * 0.5;
    const bottom = view.el.scrollTop + view.el.clientHeight * 1.5;
    let first = 0;
    while (first < count && offsets[first + 1] < top) first++;
    let last = first;
    while (last < count && offsets[last] < bottom) last++;
    return [first, last];
  }
  refill(view) {
    if (!view.el.clientHeight) return;
    const [first, last] = this.visibleRange(view);
    for (const [index, row] of [...view.rows]) {
      if (index < first || index >= last) this.unbind(view, index, row);
    }
    for (let index = first; index < last; index++) {
      if (!view.rows.has(index)) this.bind(view, index);
    }
  }
  async bind(view, index) {
    const key = view.freeKeys.length ? view.freeKeys.pop() : view.nextKey++;
    const container = document.createElement("div");
    container.className = "pn-vlist-row";
    if (view.props.separator !== false) container.classList.add("pn-separator");
    container.style.top = px(view.offsets[index]);
    container.style.height = px(view.offsets[index + 1] - view.offsets[index]);
    view.spacer.appendChild(container);
    const row = { key, container, root: null };
    view.rows.set(index, row);
    const payload = { container: key, index, width: view.el.clientWidth, height: view.offsets[index + 1] - view.offsets[index] };
    const reply = await view.ctx.request(view.tag, "on_bind_row", [payload]);
    if (view.rows.get(index) !== row) return; // recycled meanwhile
    let rootTag = null;
    try {
      const parsed = typeof reply === "string" ? JSON.parse(reply) : reply;
      rootTag = parsed && parsed.root != null ? Number(parsed.root) : null;
    } catch (err) {
      rootTag = null;
    }
    if (rootTag == null) return;
    const rootView = view.ctx.viewFor(rootTag);
    if (!rootView) return;
    row.root = rootView;
    container.appendChild(rootView.el);
  }
  unbind(view, index, row) {
    view.rows.delete(index);
    row.container.remove();
    view.freeKeys.push(row.key);
    view.ctx.emit(view.tag, "on_unbind_row", [{ container: row.key }]);
  }
  command(view, name, args) {
    const el = view.el;
    const behavior = args.animated !== false ? "smooth" : "auto";
    switch (name) {
      case "scroll_to_offset":
        el.scrollTo({ top: Number(args.y ?? args.offset) || 0, behavior });
        return null;
      case "scroll_to_index": {
        const index = Math.max(0, Math.min(view.offsets.length - 2, Number(args.index) || 0));
        let top = view.offsets[index] || 0;
        const position = args.position;
        const rowH = (view.offsets[index + 1] || 0) - top;
        if (position === "middle" || position === "center") top -= (el.clientHeight - rowH) / 2;
        else if (position === "bottom" || position === "end") top -= el.clientHeight - rowH;
        el.scrollTo({ top: Math.max(0, top), behavior });
        return null;
      }
      case "scroll_to_end":
        el.scrollTo({ top: el.scrollHeight, behavior });
        return null;
      case "get_scroll_offset":
        return { x: el.scrollLeft, y: el.scrollTop };
      case "reload":
        this.reload(view);
        return null;
      default:
        return null;
    }
  }
  destroy(view) {
    for (const [index, row] of [...view.rows]) this.unbind(view, index, row);
  }
}

class PlaceholderManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view pn-placeholder";
    el.textContent = view.type;
    el.title = `No browser implementation for ${view.type}; it renders natively on device.`;
    view.el = el;
    this.update(view, props);
  }
  measure(view, maxW) {
    return [Math.min(isFiniteConstraint(maxW) ? maxW : 120, 120), 32];
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
};

// ---------------------------------------------------------------------------
// Animations (PNAnimator equivalent)
// ---------------------------------------------------------------------------

const EASINGS = {
  linear: (t) => t,
  ease_in: (t) => t * t,
  ease_in_quad: (t) => t * t,
  ease_out: (t) => 1 - (1 - t) * (1 - t),
  ease_out_quad: (t) => 1 - (1 - t) * (1 - t),
  ease: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
  ease_in_out: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
  bounce: (t) => {
    const n1 = 7.5625;
    const d1 = 2.75;
    if (t < 1 / d1) return n1 * t * t;
    if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
    if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
    return n1 * (t -= 2.625 / d1) * t + 0.984375;
  },
};

function cubicBezier(x1, y1, x2, y2) {
  const sample = (t, a, b) => 3 * a * (1 - t) * (1 - t) * t + 3 * b * (1 - t) * t * t + t * t * t;
  return (x) => {
    let lo = 0;
    let hi = 1;
    let t = x;
    for (let i = 0; i < 24; i++) {
      const cx = sample(t, x1, x2);
      if (Math.abs(cx - x) < 1e-4) break;
      if (cx < x) lo = t;
      else hi = t;
      t = (lo + hi) / 2;
    }
    return sample(t, y1, y2);
  };
}

const ANIM_TRANSFORM = new Set(["translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate"]);

class Animator {
  constructor(renderer) {
    this.renderer = renderer;
    this.active = new Map(); // id -> {view, prop, cancel}
  }
  set(view, prop, value) {
    if (ANIM_TRANSFORM.has(prop)) {
      view.animTransform = view.animTransform || {};
      view.animTransform[prop] = Number(value) || 0;
      composeTransform(view);
    } else if (prop === "opacity") {
      view.el.style.opacity = String(value);
    } else if (prop === "background_color") {
      view.el.style.backgroundColor = parseColor(value, this.renderer.ctx.scheme()) ?? "";
    } else if (prop === "color") {
      view.el.style.color = parseColor(value, this.renderer.ctx.scheme()) ?? "";
    }
    view.animValues = view.animValues || {};
    view.animValues[prop] = value;
  }
  current(view, prop) {
    if (view.animValues && prop in view.animValues) return view.animValues[prop];
    if (prop === "opacity") return view.el.style.opacity === "" ? 1 : Number(view.el.style.opacity);
    if (prop === "scale" || prop === "scale_x" || prop === "scale_y") return 1;
    return 0;
  }
  start(view, id, prop, spec) {
    if (!spec || typeof spec !== "object") return false;
    const kind = spec.kind;
    const isColor = prop === "background_color" || prop === "color";
    if (isColor) return false; // color interpolation stays on the Python ticker
    const from = spec.from != null ? Number(spec.from) : Number(this.current(view, prop)) || 0;
    let step;
    let finished = false;
    if (kind === "timing") {
      const to = Number(spec.to);
      const duration = Math.max(1, Number(spec.duration_ms) || 300);
      let easing = EASINGS.ease_in_out;
      if (Array.isArray(spec.easing) && spec.easing.length === 4) easing = cubicBezier(...spec.easing.map(Number));
      else if (typeof spec.easing === "string" && EASINGS[spec.easing]) easing = EASINGS[spec.easing];
      step = (elapsed) => {
        const t = Math.min(1, elapsed / duration);
        const value = from + (to - from) * easing(t);
        return [value, t >= 1];
      };
    } else if (kind === "spring") {
      const to = Number(spec.to);
      const stiffness = Number(spec.stiffness) || 100;
      const damping = Number(spec.damping) || 10;
      const mass = Number(spec.mass) || 1;
      let position = from;
      let velocity = Number(spec.initial_velocity) || 0;
      let last = 0;
      step = (elapsed) => {
        const dt = Math.min(0.064, (elapsed - last) / 1000);
        last = elapsed;
        const steps = Math.max(1, Math.ceil(dt / 0.004));
        const h = dt / steps;
        for (let i = 0; i < steps; i++) {
          const force = -stiffness * (position - to) - damping * velocity;
          velocity += (force / mass) * h;
          position += velocity * h;
        }
        const done = Math.abs(velocity) < 0.01 && Math.abs(position - to) < 0.01;
        return [done ? to : position, done];
      };
    } else if (kind === "decay") {
      let velocity = Number(spec.velocity) || 0; // units per second
      const deceleration = Number(spec.deceleration) || 0.997;
      let position = from;
      let last = 0;
      step = (elapsed) => {
        const dt = elapsed - last;
        last = elapsed;
        const factor = Math.pow(deceleration, dt);
        position += (velocity * (1 - factor)) / (1000 * (1 - deceleration));
        velocity *= factor;
        return [position, Math.abs(velocity) < 0.5];
      };
    } else {
      return false;
    }
    const delay = Number(spec.delay_ms) || 0;
    const startedAt = performance.now() + delay;
    const handle = { view, prop, frame: 0 };
    const tick = (now) => {
      if (!this.active.has(id)) return;
      if (now < startedAt) {
        handle.frame = requestAnimationFrame(tick);
        return;
      }
      const [value, done] = step(now - startedAt);
      this.set(view, prop, value);
      if (done) {
        finished = true;
        this.active.delete(id);
        this.renderer.ctx.animationFinished(id, true);
        return;
      }
      handle.frame = requestAnimationFrame(tick);
    };
    this.active.set(id, handle);
    handle.frame = requestAnimationFrame(tick);
    return true;
  }
  cancel(id) {
    const handle = this.active.get(id);
    if (!handle) return null;
    this.active.delete(id);
    cancelAnimationFrame(handle.frame);
    this.renderer.ctx.animationFinished(id, false);
    return { value: this.current(handle.view, handle.prop) };
  }
  cancelForView(view) {
    for (const [id, handle] of [...this.active]) {
      if (handle.view === view) {
        this.active.delete(id);
        cancelAnimationFrame(handle.frame);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Gestures: forward pointer streams to the Python arbiter
// ---------------------------------------------------------------------------

function installGestureSource(view) {
  if (view.gestureInstalled) return;
  view.gestureInstalled = true;
  const el = view.el;
  const send = (phase, event) => {
    const point = view.ctx.pointInFrame(event);
    view.ctx.gesture(view.tag, phase, { id: event.pointerId, x: point.x, y: point.y, specs: view.props.gestures || [] });
  };
  el.addEventListener("pointerdown", (event) => {
    if (!Array.isArray(view.props.gestures) || !view.props.gestures.length) return;
    try {
      el.setPointerCapture(event.pointerId);
    } catch (err) {
      /* ignore */
    }
    view.gestureActive = true;
    send("down", event);
  });
  el.addEventListener("pointermove", (event) => {
    if (view.gestureActive) send("move", event);
  });
  el.addEventListener("pointerup", (event) => {
    if (!view.gestureActive) return;
    view.gestureActive = false;
    send("up", event);
  });
  el.addEventListener("pointercancel", (event) => {
    if (!view.gestureActive) return;
    view.gestureActive = false;
    send("cancel", event);
  });
}

// ---------------------------------------------------------------------------
// The renderer
// ---------------------------------------------------------------------------

export class Renderer {
  /**
   * @param ctx {{
   *   emit(tag, name, args), request(tag, name, args), gesture(tag, phase, info),
   *   animationFinished(id, finished), scheme(), overlays(), bottomInset(),
   *   frameWidth(), pointInFrame(event), statusBar(opts)
   * }}
   */
  constructor(ctx) {
    this.ctx = ctx;
    this.ctx.viewFor = (tag) => this.views.get(tag) || null;
    this.views = new Map();
    this.managers = {};
    this.animator = new Animator(this);
    this.dirtyContainers = new Set();
    for (const [name, Manager] of Object.entries(MANAGERS)) this.managers[name] = new Manager();
    this.placeholder = new PlaceholderManager();
    this.warnedTypes = new Set();
  }

  reset() {
    for (const view of this.views.values()) {
      try {
        view.manager.destroy(view);
      } catch (err) {
        /* ignore */
      }
      view.el.remove();
    }
    this.views.clear();
    this.animator.active.clear();
  }

  // -- transactions ------------------------------------------------------

  apply(ops) {
    if (!Array.isArray(ops)) return;
    for (const op of ops) {
      try {
        this.applyOne(op);
      } catch (err) {
        console.error("[pn] op failed", op, err);
      }
    }
    for (const view of this.dirtyContainers) {
      if (this.views.has(view.tag)) view.manager.childrenChanged(view);
    }
    this.dirtyContainers.clear();
  }

  applyOne(op) {
    switch (op[0]) {
      case "c": {
        const [, tag, type, props] = op;
        const manager = this.managers[type] || this.placeholder;
        if (manager === this.placeholder && !this.warnedTypes.has(type)) {
          this.warnedTypes.add(type);
          console.warn(`[pn] no browser renderer for element type ${type}; drawing a placeholder`);
        }
        const view = {
          tag,
          type,
          props: { ...(props || {}) },
          manager,
          ctx: this.ctx,
          children: [],
          parent: null,
          frame: null,
          el: null,
          hasEvent: null,
        };
        view.hasEvent = (name) => Array.isArray(view.props._pn_events) && view.props._pn_events.includes(name);
        manager.create(view, view.props);
        view.el.dataset.pnTag = String(tag);
        view.el.dataset.pnType = type;
        if (Array.isArray(view.props.gestures) && view.props.gestures.length) installGestureSource(view);
        this.views.set(tag, view);
        return;
      }
      case "u": {
        const [, tag, changed] = op;
        const view = this.views.get(tag);
        if (!view || !changed) return;
        for (const [key, value] of Object.entries(changed)) {
          if (value === null || value === undefined) delete view.props[key];
          else view.props[key] = value;
        }
        view.manager.update(view, changed);
        if ("gestures" in changed) {
          if (Array.isArray(view.props.gestures) && view.props.gestures.length) installGestureSource(view);
          else this.ctx.gesture(tag, "clear", {});
        }
        return;
      }
      case "i": {
        const [, parentTag, childTag, index] = op;
        const parent = this.views.get(parentTag);
        const child = this.views.get(childTag);
        if (!parent || !child) return;
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
        return;
      }
      case "d": {
        const [, tag] = op;
        const view = this.views.get(tag);
        if (!view) return;
        this.destroyView(view);
        return;
      }
      case "f": {
        const [, tag, x, y, w, h] = op;
        const view = this.views.get(tag);
        if (!view) return;
        const finite = [x, y, w, h].every((v) => Number.isFinite(v));
        if (!finite) return;
        view.frame = { x, y, w, h };
        view.manager.frame(view, x, y, w, h);
        if (view.parent) this.dirtyContainers.add(view.parent);
        return;
      }
      default:
        console.warn("[pn] unknown op", op);
    }
  }

  destroyView(view) {
    this.animator.cancelForView(view);
    for (const child of [...view.children]) this.destroyView(child);
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
    this.ctx.gesture(view.tag, "clear", {});
  }

  // -- synchronous requests ---------------------------------------------

  measure(tag, maxW, maxH) {
    const view = this.views.get(tag);
    if (!view) return [0, 0];
    try {
      const [w, h] = view.manager.measure(view, maxW, maxH);
      return [Number.isFinite(w) ? w : 0, Number.isFinite(h) ? h : 0];
    } catch (err) {
      console.error("[pn] measure failed", tag, err);
      return [0, 0];
    }
  }

  command(tag, name, argsJson) {
    const view = this.views.get(tag);
    if (!view) return null;
    let args = {};
    try {
      args = argsJson ? JSON.parse(argsJson) || {} : {};
    } catch (err) {
      args = {};
    }
    const result = view.manager.command(view, name, args);
    return result === undefined ? null : result;
  }

  animate(tag, requestJson) {
    const view = this.views.get(tag);
    let request;
    try {
      request = JSON.parse(requestJson);
    } catch (err) {
      return null;
    }
    if (!request || typeof request !== "object") return null;
    if (request.op === "cancel") return this.animator.cancel(request.id);
    if (!view) return request.op === "start" ? { ok: false } : null;
    if (request.op === "set") {
      this.animator.set(view, request.prop, request.value);
      return null;
    }
    if (request.op === "start") {
      return { ok: this.animator.start(view, request.id, request.prop, request.spec) };
    }
    return null;
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
