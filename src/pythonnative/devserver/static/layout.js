import Yoga from "./yoga/src/index.js";

const detached = new Set(["VirtualList", "Modal", "Portal", "ScreenStack"]);
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
function style(node, props) {
  const fresh = Yoga.Node.create();
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (enums[key]) {
      const [name, values] = enums[key];
      const index = values.indexOf(value);
      if (index < 0) throw Error(`Invalid ${key}: ${value}`);
      fresh[`set${name}`](index);
    } else if (["width", "height", "min_width", "min_height", "max_width", "max_height", "flex", "flex_grow", "flex_shrink", "flex_basis", "aspect_ratio"].includes(key)) {
      fresh["set" + key.split("_").map(p => p[0].toUpperCase() + p.slice(1)).join("")](value);
    } else if (["gap", "spacing", "row_gap", "column_gap"].includes(key)) {
      fresh.setGap({row_gap:1, column_gap:0}[key] ?? 2, value);
    } else if (["left", "right", "top", "bottom", "start", "end"].includes(key)) fresh.setPosition(edges[key], value);
    else if (key.startsWith("padding") || key.startsWith("margin")) {
      const [group, edge] = key.split("_");
      const name = group === "padding" ? "setPadding" : "setMargin";
      if (typeof value === "object") for (const [side, amount] of Object.entries(value)) fresh[name](edges[side], amount);
      else fresh[name](edges[edge || "all"], value);
    } else if (key.startsWith("border_") && key.endsWith("width")) fresh.setBorder(edges[key.split("_")[1]] ?? 8, value);
  }
  node.copyStyle(fresh);
  fresh.free();
}
export function disposeLayout(view) {
  if (!view.yoga) return;
  const parent = view.yoga.getParent();
  if (parent) parent.removeChild(view.yoga);
  view.yoga.free(); view.yoga = null;
}
export function computeLayout(renderer, {roots = [], width, height}) {
  const views = [...renderer.views.values()];
  for (const view of views) {
    view.yoga ||= Yoga.Node.create();
    const props = JSON.stringify(view.props);
    if (props !== view.yogaProps) {
      style(view.yoga, view.props); view.yogaProps = props;
      if (["ScrollView", "VirtualList", "ScreenStack"].includes(view.type)) { view.yoga.setOverflow(1); view.yoga.setFlexShrink(1); }
    }
    while (view.yoga.getChildCount()) view.yoga.removeChild(view.yoga.getChild(0));
    view.yoga.unsetMeasureFunc();
  }
  for (const view of views) {
    if (!detached.has(view.type)) for (const child of view.children) view.yoga.insertChild(child.yoga, view.yoga.getChildCount());
    if (!view.yoga.getChildCount() && !containers.has(view.type)) view.yoga.setMeasureFunc((w, wm, h, hm) => {
      const [width, height] = view.manager.measure(view, wm ? w : 1e6, hm ? h : 1e6);
      return {width, height};
    });
  }
  for (const tag of roots) renderer.views.get(tag)?.yoga.calculateLayout(width, height, 1);
  for (const view of views) if (view.parent && !view.yoga.getParent()) {
    const parent = view.parent;
    const isList = parent.type === "VirtualList", horizontal = parent.props.horizontal;
    view.yoga.calculateLayout(isList && horizontal ? NaN : parent.frame?.w || width,
      isList && !horizontal ? NaN : parent.frame?.h || height, 1);
  }
  const frames = [];
  for (const view of views) {
    const layout = view.yoga.getComputedLayout();
    const frame = [layout.left, layout.top, layout.width, layout.height];
    if (JSON.stringify(frame) === view.layoutFrame) continue;
    view.layoutFrame = JSON.stringify(frame);
    view.frame = {x:frame[0], y:frame[1], w:frame[2], h:frame[3]};
    if (!roots.includes(view.tag)) view.manager.frame(view, ...frame);
    frames.push([view.tag, ...frame]);
  }
  for (const view of views) if (view.children.length) view.manager.childrenChanged(view);
  return frames;
}
