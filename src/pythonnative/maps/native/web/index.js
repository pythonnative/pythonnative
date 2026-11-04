// `MapView` in the browser preview: a labeled plate with the markers and lines
// in their relative places. There are no tiles, so nothing leaves the page.

import { ViewManager } from "/static/renderer.js";

const SVG = "http://www.w3.org/2000/svg";
const WORLD = { center: { latitude: 0, longitude: 0 }, latitude_delta: 140, longitude_delta: 360 };

function element(tag, attributes = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

class MapManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.overflow = "hidden";
    el.style.background = "#E8EEF2";
    view.el = el;
    view.svg = element("svg");
    view.svg.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
    const label = document.createElement("div");
    label.textContent = "Map preview: no tiles in the browser";
    label.style.cssText = "position:absolute;left:8px;top:8px;font:12px system-ui;color:#475569;pointer-events:none";
    el.append(view.svg, label);
    view.size = [0, 0];
    view.region = props.region || props.initial_region || WORLD;
    el.addEventListener("click", (event) => {
      if (!view.hasEvent("on_press") || event.target.dataset?.marker) return;
      const box = el.getBoundingClientRect();
      view.ctx.emit(view.tag, "on_press", [this.unproject(view, event.clientX - box.left, event.clientY - box.top)]);
    });
    this.update(view, props);
    // The tag isn't registered for events until `create` returns.
    setTimeout(() => { if (view.hasEvent("on_ready")) view.ctx.emit(view.tag, "on_ready", []); });
  }

  update(view, changed) {
    super.update(view, changed);
    if (changed.region && JSON.stringify(changed.region) !== JSON.stringify(view.region)) this.move(view, changed.region);
    this.draw(view);
  }

  frame(view, x, y, w, h) {
    super.frame(view, x, y, w, h);
    view.size = [w, h];
    this.draw(view);
  }

  command(view, name, args) {
    if (name !== "animate_to") return super.command(view, name, args);
    this.move(view, args.region);
    this.draw(view);
    return null;
  }

  move(view, region) {
    view.region = region;
    if (view.hasEvent("on_region_change")) view.ctx.emit(view.tag, "on_region_change", [region]);
  }

  project(view, { latitude, longitude }) {
    const { center, latitude_delta: height, longitude_delta: width } = view.region;
    return [
      (0.5 + (longitude - center.longitude) / width) * view.size[0],
      (0.5 - (latitude - center.latitude) / height) * view.size[1],
    ];
  }

  unproject(view, x, y) {
    const { center, latitude_delta: height, longitude_delta: width } = view.region;
    return {
      latitude: center.latitude + (0.5 - y / view.size[1]) * height,
      longitude: center.longitude + (x / view.size[0] - 0.5) * width,
    };
  }

  draw(view) {
    const [width, height] = view.size;
    view.svg.replaceChildren();
    if (!width || !height) return;
    for (let step = 1; step < 4; step += 1) {
      const line = { stroke: "#CBD5E1", "stroke-width": 1 };
      view.svg.append(element("line", { ...line, x1: (width * step) / 4, x2: (width * step) / 4, y1: 0, y2: height }));
      view.svg.append(element("line", { ...line, x1: 0, x2: width, y1: (height * step) / 4, y2: (height * step) / 4 }));
    }
    for (const polyline of view.props.polylines || []) {
      view.svg.append(element("polyline", {
        points: polyline.coordinates.map((point) => this.project(view, point).join(",")).join(" "),
        fill: "none",
        stroke: polyline.color || "#1A73E8",
        "stroke-width": polyline.width ?? 2,
      }));
    }
    for (const marker of view.props.markers || []) {
      const [x, y] = this.project(view, marker.coordinate);
      const pin = element("circle", { cx: x, cy: y, r: 7, fill: marker.color || "#EA4335", stroke: "#FFFFFF", "stroke-width": 2 });
      pin.dataset.marker = marker.id;
      pin.style.cursor = "pointer";
      const title = element("title");
      title.textContent = marker.title || marker.id;
      pin.append(title);
      pin.addEventListener("click", () => {
        if (view.hasEvent("on_marker_press")) view.ctx.emit(view.tag, "on_marker_press", [marker.id]);
      });
      view.svg.append(pin);
    }
  }
}

export const components = { MapView: MapManager };
