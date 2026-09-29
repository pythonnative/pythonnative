import Yoga from "./yoga/src/index.js";

const detached = new Set(["VirtualList", "Modal", "Portal", "ScreenStack"]);

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
const containers = new Set([...detached, "View", "Row", "Column", "ScrollView", "Screen"]);
const edges = {left:0, top:1, right:2, bottom:3, start:4, end:5, horizontal:6, vertical:7, all:8};
const enums = {
  direction: ["Direction", ["inherit", "ltr", "rtl"]],
  flex_direction: ["FlexDirection", ["column", "column_reverse", "row", "row_reverse"]],
  justify_content: ["JustifyContent", ["flex_start", "center", "flex_end", "space_between", "space_around", "space_evenly"]],
  align_items: ["AlignItems", ["auto", "flex_start", "center", "flex_end", "stretch", "baseline", "space_between", "space_around", "space_evenly"]],
  align_self: ["AlignSelf", ["auto", "flex_start", "center", "flex_end", "stretch", "baseline", "space_between", "space_around", "space_evenly"]],
  align_content: ["AlignContent", ["auto", "flex_start", "center", "flex_end", "stretch", "baseline", "space_between", "space_around", "space_evenly"]],
  position: ["PositionType", ["static", "relative", "absolute"]],
  flex_wrap: ["FlexWrap", ["nowrap", "wrap", "wrap_reverse"]],
  display: ["Display", ["flex", "none", "contents"]],
};

const defaults = {direction:0, flex_direction:0, justify_content:0, align_items:4, align_self:0, align_content:1, position:1, flex_wrap:0, display:0};
function property(node, key, value) {
  if (enums[key]) {
    const [name, values] = enums[key];
    const index = value == null ? defaults[key] : values.indexOf(value);
    if (index < 0) throw Error(`Invalid ${key}: ${value}`);
    node[`set${name}`](index);
  } else if (["width", "height", "min_width", "min_height", "max_width", "max_height", "flex", "flex_grow", "flex_shrink", "flex_basis", "aspect_ratio"].includes(key)) {
    node["set" + key.split("_").map(p => p[0].toUpperCase() + p.slice(1)).join("")](value ?? (["width", "height", "flex_basis"].includes(key) ? "auto" : NaN));
  } else if (["gap", "spacing", "row_gap", "column_gap"].includes(key)) node.setGap({row_gap:1, column_gap:0}[key] ?? 2, value ?? NaN);
  else if (["left", "right", "top", "bottom", "start", "end"].includes(key)) node.setPosition(edges[key], value ?? NaN);
  else if (key.startsWith("border_") && key.endsWith("width")) node.setBorder(edges[key.split("_")[1]] ?? 8, value ?? NaN);
}
function measurement(view) {
  const needed = !view.yoga.getChildCount() && !containers.has(view.type);
  if (needed === !!view.yogaMeasured) return;
  view.yogaMeasured = needed;
  if (!needed) view.yoga.unsetMeasureFunc();
  else view.yoga.setMeasureFunc((w, wm, h, hm) => {
    const [width, height] = view.manager.measure(view, wm ? w : 1e6, hm ? h : 1e6);
    return {width, height};
  });
}
export function updateLayout(view, changed, removed = [], affectsMeasurement = true) {
  view.yoga ||= Yoga.Node.create();
  const touched = new Set([...Object.keys(changed), ...removed]);
  if (changed._pn_layout) view.requestLayoutFrame = true;
  for (const family of ["margin", "padding"]) if ([...touched].some(key => key === family || key.startsWith(family + "_"))) {
    const values = {}, source = view.props[family];
    if (source && typeof source === "object") Object.assign(values, source);
    else if (source != null) values.all = source;
    for (const edge of Object.keys(edges)) if (edge !== "all" && view.props[`${family}_${edge}`] != null) values[edge] = view.props[`${family}_${edge}`];
    for (const [edge, index] of Object.entries(edges)) {
      view.yoga[family === "margin" ? "setMargin" : "setPadding"](index, values[edge] ?? NaN);
      touched.delete(edge === "all" ? family : `${family}_${edge}`);
    }
  }
  if (touched.has("gap") || touched.has("spacing")) {
    property(view.yoga, "gap", view.props.gap ?? view.props.spacing);
    touched.delete("gap"); touched.delete("spacing");
  }
  for (const key of touched) property(view.yoga, key, view.props[key]);
  if (["ScrollView", "VirtualList", "ScreenStack"].includes(view.type)) {
    view.yoga.setOverflow(1);
    if (view.props.flex_shrink == null) view.yoga.setFlexShrink(1);
  }
  measurement(view);
  if (affectsMeasurement && view.yogaMeasured) view.yoga.markDirty();
}
export function insertLayout(renderer, parent, child) {
  renderer.layoutDetached ||= new Set();
  const old = child.yoga.getParent();
  if (old) old.removeChild(child.yoga);
  child.layoutParent = null;
  if (detached.has(parent.type) || child.props._pn_header_slot) renderer.layoutDetached.add(child);
  else {
    if (parent.yogaMeasured) { parent.yoga.unsetMeasureFunc(); parent.yogaMeasured = false; }
    const index = parent.children.slice(0, parent.children.indexOf(child)).filter(item => !item.props._pn_header_slot).length;
    parent.yoga.insertChild(child.yoga, index);
    child.layoutParent = parent;
    renderer.layoutDetached.delete(child);
  }
}
export function disposeLayout(view) {
  if (!view.yoga) return;
  const parent = view.yoga.getParent();
  if (parent) parent.removeChild(view.yoga);
  view.yoga.free(); view.yoga = null;
}
export function computeLayout(renderer, {roots = [], width, height, selective = false}) {
  const rootTags = new Set(roots), detachedRoots = renderer.layoutDetached || new Set();
  const frames = [], changedParents = new Set();
  let visited = 0;
  function collect(view) {
    if (!view?.yoga?.hasNewLayout()) return;
    visited++; view.yoga.markLayoutSeen();
    const layout = view.yoga.getComputedLayout();
    const frame = [layout.left, layout.top, layout.width, layout.height];
    if (!view.layoutFrame || frame.some((value, i) => value !== view.layoutFrame[i]) || view.requestLayoutFrame) {
      view.layoutFrame = frame; view.requestLayoutFrame = false;
      view.frame = {x:frame[0], y:frame[1], w:frame[2], h:frame[3]};
      if (!rootTags.has(view.tag)) view.manager.frame(view, ...frame);
      if (!selective || view.props._pn_layout) frames.push([view.tag, ...frame]);
      if (view.parent) changedParents.add(view.parent);
      if (view.children.length) changedParents.add(view);
    }
    for (const child of view.children) if (child.layoutParent === view) collect(child);
  }
  for (const tag of roots) renderer.views.get(tag)?.yoga.calculateLayout(width, height, 1);
  for (const tag of roots) collect(renderer.views.get(tag));
  for (const view of detachedRoots) {
    if (!renderer.views.has(view.tag) || !view.parent) continue;
    const parent = view.parent;
    if (view.props._pn_header_slot) { view.yoga.calculateLayout(NaN, STACK_HEADER, 1); collect(view); continue; }
    const isList = parent.type === "VirtualList", horizontal = parent.props.horizontal;
    const inset = parent.type === "ScreenStack" ? stackHeaderHeight(view.props) : 0;
    view.yoga.calculateLayout(isList && horizontal ? NaN : parent.frame?.w || width,
      isList && !horizontal ? NaN : Math.max(0, (parent.frame?.h || height) - inset), 1);
    collect(view);
  }

  for (const view of renderer.layoutObservers || []) {
    if (view.requestLayoutFrame && view.layoutFrame) { frames.push([view.tag, ...view.layoutFrame]); view.requestLayoutFrame = false; }
  }
  renderer.layoutObservers.clear();
  for (const view of changedParents) view.manager.childrenChanged(view);
  renderer.layoutVisited = visited;
  return frames;
}
