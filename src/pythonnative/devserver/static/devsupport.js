// The preview's `DevSupport` module: the browser counterpart of the
// native development UI (RFC 0006). Python's devtools agent drives it:
//
// - `enable()`: start listening for dev menu triggers.
// - `highlight({tag, label})`: outline a view and label it (`tag: null`
//   clears the outline).
// - `set_inspecting({enabled})`: capture clicks on the phone screen and
//   report the clicked view as an `inspect` event `{tag, x, y}`; the
//   banner's Done button sends `inspect_done`.
// - `set_perf_monitor({visible, lines})`: the floating monitor, whose
//   first line is the page's own frame rate.
// - `frame_stats()`: `{fps, dropped}` since the previous call.
//
// Overlays live in the frame's overlay layer, so they scale and clip with
// the phone. Views are found through the `data-pn-tag` attribute the
// renderer puts on every view's element.

const FRAME_MS = 1000 / 60;

/** Counts animation frames to report a frame rate and dropped frames. */
export class FrameMeter {
  constructor() {
    this.frames = 0;
    this.dropped = 0;
    this.since = 0;
    this.last = 0;
    this.handle = 0;
    this.users = 0;
    this.tick = this.tick.bind(this);
  }

  acquire() {
    this.users += 1;
    if (this.users === 1) {
      this.reset(performance.now());
      this.handle = requestAnimationFrame(this.tick);
    }
  }

  release() {
    this.users = Math.max(0, this.users - 1);
    if (this.users === 0 && this.handle) {
      cancelAnimationFrame(this.handle);
      this.handle = 0;
    }
  }

  reset(now) {
    this.frames = 0;
    this.dropped = 0;
    this.since = now;
    this.last = now;
  }

  tick(now) {
    const delta = now - this.last;
    if (this.frames > 0 && delta > FRAME_MS * 1.5) this.dropped += Math.max(0, Math.round(delta / FRAME_MS) - 1);
    this.frames += 1;
    this.last = now;
    this.handle = requestAnimationFrame(this.tick);
  }

  /** `{fps, dropped}` since the last call (or since `acquire`), then start a new window. */
  take(now = performance.now()) {
    const elapsed = Math.max(1, now - this.since);
    const stats = { fps: Math.round((this.frames * 1000) / elapsed), dropped: this.dropped };
    this.reset(now);
    return stats;
  }
}

export class DevSupport {
  /**
   * @param host The `PreviewHost`: supplies `screensEl`, `overlaysEl`,
   *   `moduleEvent`, and `presentAlert`.
   */
  constructor(host) {
    this.host = host;
    this.enabled = false;
    this.inspecting = false;
    this.highlighted = null; // {tag, label}
    this.hovered = null; // tag under the pointer while inspecting
    this.highlightEl = null;
    this.hoverEl = null;
    this.catcher = null;
    this.banner = null;
    this.monitor = null;
    this.monitorLines = [];
    this.meter = new FrameMeter();
    this.statsMeter = null;
    this.trackHandle = 0;
    this.track = this.track.bind(this);
  }

  /** The methods Python may call, as the host's module table expects them. */
  module() {
    const methods = {};
    for (const name of ["enable", "highlight", "set_inspecting", "set_perf_monitor", "frame_stats"]) {
      methods[name] = (args) => this[name](args || {});
    }
    return methods;
  }

  // -- module methods ---------------------------------------------------

  enable() {
    this.enabled = true;
    return null;
  }

  highlight({ tag, label } = {}) {
    if (tag == null) {
      this.highlighted = null;
      this.highlightEl?.remove();
      this.highlightEl = null;
    } else {
      this.highlighted = { tag: Number(tag), label: label == null ? "" : String(label) };
      if (!this.highlightEl) this.highlightEl = outline("pn-dev-highlight");
    }
    this.syncTracking();
    return null;
  }

  set_inspecting({ enabled } = {}) {
    const on = !!enabled;
    if (on === this.inspecting) return null;
    this.inspecting = on;
    if (on) this.showInspector();
    else this.hideInspector();
    return null;
  }

  set_perf_monitor({ visible, lines } = {}) {
    this.monitorLines = Array.isArray(lines) ? lines.map(String) : [];
    if (visible) {
      if (!this.monitor) {
        this.monitor = document.createElement("div");
        this.monitor.className = "pn-dev-monitor";
        this.monitor.setAttribute("aria-hidden", "true");
        this.meter.acquire();
        this.monitorTimer = setInterval(() => this.renderMonitor(true), 1000);
        this.monitorFps = null;
      }
      this.host.overlaysEl.appendChild(this.monitor);
      this.renderMonitor(false);
    } else if (this.monitor) {
      clearInterval(this.monitorTimer);
      this.meter.release();
      this.monitor.remove();
      this.monitor = null;
    }
    return null;
  }

  /** `{fps, dropped}` since the previous call; the first call starts measuring. */
  frame_stats() {
    if (!this.statsMeter) {
      this.statsMeter = new FrameMeter();
      this.statsMeter.acquire();
      return { fps: 0, dropped: 0 };
    }
    return this.statsMeter.take();
  }

  // -- triggers ---------------------------------------------------------

  /** Ask Python to show the dev menu (toolbar button, Cmd/Ctrl+D). */
  requestMenu() {
    this.host.moduleEvent("DevSupport", "menu", {});
  }

  // -- inspector --------------------------------------------------------

  showInspector() {
    const catcher = document.createElement("div");
    catcher.className = "pn-dev-inspect-catcher";
    catcher.addEventListener("pointermove", (event) => {
      const found = this.viewAt(event.clientX, event.clientY);
      this.hovered = found ? Number(found.dataset.pnTag) : null;
      this.syncTracking();
    });
    catcher.addEventListener("pointerleave", () => {
      this.hovered = null;
      this.syncTracking();
    });
    catcher.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const found = this.viewAt(event.clientX, event.clientY);
      if (!found) return;
      const point = this.framePoint(event.clientX, event.clientY);
      this.host.moduleEvent("DevSupport", "inspect", { tag: Number(found.dataset.pnTag), x: point.x, y: point.y });
    });

    const banner = document.createElement("div");
    banner.className = "pn-dev-inspect-banner";
    banner.setAttribute("role", "status");
    const text = document.createElement("span");
    text.textContent = "Click an element to inspect it";
    const done = document.createElement("button");
    done.type = "button";
    done.textContent = "Done";
    done.addEventListener("click", () => {
      this.set_inspecting({ enabled: false });
      this.host.moduleEvent("DevSupport", "inspect_done", {});
    });
    banner.append(text, done);

    this.catcher = catcher;
    this.banner = banner;
    this.hoverEl = outline("pn-dev-hover");
    this.host.overlaysEl.append(catcher, banner);
  }

  hideInspector() {
    this.catcher?.remove();
    this.banner?.remove();
    this.hoverEl?.remove();
    this.catcher = this.banner = this.hoverEl = null;
    this.hovered = null;
    this.syncTracking();
  }

  /** The innermost rendered view under a page point, looking through the inspector's own layers. */
  viewAt(clientX, clientY) {
    const layers = [this.catcher, this.banner, this.highlightEl, this.hoverEl, this.monitor].filter(Boolean);
    const saved = layers.map((layer) => layer.style.pointerEvents);
    for (const layer of layers) layer.style.pointerEvents = "none";
    let hit = null;
    try {
      hit = document.elementFromPoint(clientX, clientY);
    } finally {
      layers.forEach((layer, index) => (layer.style.pointerEvents = saved[index]));
    }
    const view = hit?.closest?.("[data-pn-tag]");
    const { screensEl, overlaysEl } = this.host;
    return view && (screensEl.contains(view) || overlaysEl.contains(view)) ? view : null;
  }

  // -- geometry ---------------------------------------------------------

  /** Page coordinates to frame points (the frame may be scaled to fit). */
  framePoint(clientX, clientY) {
    const layer = this.host.overlaysEl;
    const rect = layer.getBoundingClientRect();
    const scale = layer.offsetWidth ? rect.width / layer.offsetWidth : 1;
    return { x: (clientX - rect.left) / scale, y: (clientY - rect.top) / scale };
  }

  /** The view's box in frame points, or null when it isn't on screen. */
  frameOf(tag) {
    const view = this.host.screensEl.querySelector(`[data-pn-tag="${Number(tag)}"]`) ||
      this.host.overlaysEl.querySelector(`[data-pn-tag="${Number(tag)}"]`);
    if (!view || !view.isConnected) return null;
    const box = view.getBoundingClientRect();
    if (!box.width && !box.height) return null;
    const layer = this.host.overlaysEl;
    const rect = layer.getBoundingClientRect();
    const scale = layer.offsetWidth ? rect.width / layer.offsetWidth : 1;
    return {
      x: (box.left - rect.left) / scale,
      y: (box.top - rect.top) / scale,
      width: box.width / scale,
      height: box.height / scale,
      type: view.dataset.pnType || "",
    };
  }

  /** Keep outlines glued to their views (scrolling, animation) while any is shown. */
  syncTracking() {
    const active = !!this.highlighted || this.hovered != null;
    if (active && !this.trackHandle) this.trackHandle = requestAnimationFrame(this.track);
    if (!active && this.trackHandle) {
      cancelAnimationFrame(this.trackHandle);
      this.trackHandle = 0;
    }
    this.place();
  }

  track() {
    this.place();
    this.trackHandle = requestAnimationFrame(this.track);
  }

  place() {
    const layer = this.host.overlaysEl;
    if (this.highlightEl) {
      const frame = this.highlighted ? this.frameOf(this.highlighted.tag) : null;
      position(this.highlightEl, frame, this.highlighted?.label || frame?.type || "");
      if (frame && this.highlightEl.parentNode !== layer) layer.appendChild(this.highlightEl);
    }
    if (this.hoverEl) {
      const same = this.highlighted && this.hovered === this.highlighted.tag;
      const frame = this.hovered != null && !same ? this.frameOf(this.hovered) : null;
      position(this.hoverEl, frame, frame?.type || "");
      if (frame && this.hoverEl.parentNode !== layer) layer.insertBefore(this.hoverEl, this.banner || null);
    }
  }

  // -- performance monitor -------------------------------------------------

  renderMonitor(sample) {
    if (!this.monitor) return;
    if (sample) this.monitorFps = this.meter.take().fps;
    const fps = this.monitorFps == null ? "…" : String(this.monitorFps);
    const lines = [`UI ${fps} fps`, ...this.monitorLines];
    this.monitor.textContent = "";
    lines.forEach((line, index) => {
      const row = document.createElement("div");
      row.textContent = line;
      if (index === 0) row.className = "pn-dev-monitor-fps";
      this.monitor.appendChild(row);
    });
  }

  /** Put active overlays back after the host emptied the overlay layer (a remount). */
  reattach() {
    const layer = this.host.overlaysEl;
    for (const node of [this.catcher, this.banner, this.monitor]) {
      if (node && node.parentNode !== layer) layer.appendChild(node);
    }
    this.place();
  }

  /** Drop every overlay (the page lost its app). */
  reset() {
    this.highlight({ tag: null });
    this.set_inspecting({ enabled: false });
    this.set_perf_monitor({ visible: false });
  }
}

function outline(className) {
  const box = document.createElement("div");
  box.className = `pn-dev-outline ${className}`;
  box.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "pn-dev-outline-label";
  box.appendChild(label);
  return box;
}

function position(box, frame, label) {
  if (!frame) {
    box.style.display = "none";
    return;
  }
  box.style.display = "";
  box.style.left = `${frame.x}px`;
  box.style.top = `${frame.y}px`;
  box.style.width = `${frame.width}px`;
  box.style.height = `${frame.height}px`;
  const tag = box.firstChild;
  if (tag.textContent !== label) tag.textContent = label;
  tag.style.display = label ? "" : "none";
  // Put the label inside the box when there's no room above it.
  box.classList.toggle("pn-dev-outline-inside", frame.y < 18);
}
