// Entry point for the browser preview: wires the bridge, the renderer
// core (WebAssembly), the DOM renderer, and the screen host together and
// drives the toolbar.

import { Bridge } from "./bridge.js";
import { Renderer } from "./renderer.js";
import { startCore } from "./core/mount.js";
import { PreviewHost } from "./host.js";
import { color as parseColor } from "./colors.js";
import { assets } from "./assets.js";

/**
 * The device frames. Sizes are in points. `top` is the status bar (and
 * safe area) height, `bottom` the home indicator inset, and `landscape`
 * the insets once rotated (an iPhone hides its status bar and insets both
 * sides for the sensor housing). `chrome` picks the cutout and home
 * affordance; `bezel` is [top, right, bottom, left] in portrait, and
 * `radius` is [outer, screen].
 */
const DEVICES = [
  {
    id: "iphone-15", name: "iPhone 15", platform: "ios", chrome: "island", width: 393, height: 852,
    top: 59, bottom: 34, landscape: { top: 0, left: 59, right: 59, bottom: 21 }, bezel: [12, 12, 12, 12], radius: [67, 55],
  },
  {
    id: "iphone-15-pro-max", name: "iPhone 15 Pro Max", platform: "ios", chrome: "island", width: 430, height: 932,
    top: 59, bottom: 34, landscape: { top: 0, left: 59, right: 59, bottom: 21 }, bezel: [12, 12, 12, 12], radius: [67, 55],
  },
  {
    id: "iphone-se", name: "iPhone SE", platform: "ios", chrome: "home-button", width: 375, height: 667,
    top: 20, bottom: 0, landscape: { top: 0, left: 0, right: 0, bottom: 0 }, bezel: [72, 14, 72, 14], radius: [56, 0],
  },
  {
    id: "ipad-mini", name: "iPad mini", platform: "ios", chrome: "tablet", width: 744, height: 1133,
    top: 24, bottom: 20, landscape: { top: 24, left: 0, right: 0, bottom: 20 }, bezel: [20, 20, 20, 20], radius: [42, 22],
  },
  {
    id: "pixel-8", name: "Pixel 8", platform: "android", chrome: "punch", width: 412, height: 915,
    top: 32, bottom: 24, landscape: { top: 24, left: 32, right: 0, bottom: 24 }, bezel: [11, 11, 11, 11], radius: [46, 36],
  },
  {
    id: "pixel-fold", name: "Pixel Fold (inner)", platform: "android", chrome: "punch", width: 841, height: 701,
    top: 32, bottom: 24, landscape: { top: 24, left: 32, right: 0, bottom: 24 }, bezel: [12, 12, 12, 12], radius: [32, 20],
  },
  {
    id: "responsive", name: "Fill window", platform: "ios", chrome: "none", width: 0, height: 0,
    top: 24, bottom: 0, landscape: null, bezel: [0, 0, 0, 0], radius: [0, 0],
  },
];
const DEVICE_GROUPS = [["iOS", "ios"], ["Android", "android"], ["Other", null]];

const $ = (id) => document.getElementById(id);
const px = (value) => `${value}px`;

class Shell {
  constructor() {
    this.frame = $("pn-device-frame");
    this.screens = $("pn-screens");
    this.overlays = $("pn-overlays");
    this.statusbar = $("pn-statusbar");
    this.home = $("pn-home");
    this.stage = $("pn-stage");
    this.connect = $("pn-connect");
    this.consoleEl = $("pn-console");
    this.consoleLines = $("pn-console-lines");
    this.toasts = $("pn-toasts");
    this.unreadErrors = 0;

    const saved = this.loadPrefs();
    this.device = DEVICES.find((d) => d.id === saved.device) || DEVICES[0];
    this.landscape = !!saved.landscape;
    this.scheme = saved.scheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    this.consoleHeight = Number(saved.consoleHeight) || 0;
    this.scale = 1;
    this.statusBarState = { hidden: false, light: false, dark: false };
    this.entry = null;
    this.project = "";

    const wsScheme = location.protocol === "https:" ? "wss" : "ws";
    this.bridge = new Bridge(`${wsScheme}://${location.host}/ws?role=preview`);
    this.renderer = new Renderer(this.rendererContext());
    this.host = new PreviewHost({
      bridge: this.bridge,
      renderer: this.renderer,
      screensEl: this.screens,
      overlaysEl: this.overlays,
      frameMetrics: () => this.frameMetrics(),
      deviceName: () => this.device.name,
      projectName: () => this.project,
      scheme: () => this.scheme,
      color: (value) => parseColor(value, this.scheme),
      log: (level, text) => this.logLine(level, text),
      toast: (text, kind) => this.toast(text, kind),
    });

    this.installBridgeHandlers();
    this.installToolbar();
    this.installConsole();
    this.applyDevice();
    this.applyScheme();
    this.startClock();
    // The stage shrinks when the console opens or resizes, not only with the window.
    new ResizeObserver(() => this.fitFrame()).observe(this.stage);
    // The renderer core runs in the page; connect once it's instantiated.
    startCore(this.renderer, { send: (kind, tag, name, payload) => this.bridge.callback(kind, tag, name, payload) })
      .then((core) => {
        this.core = core;
        this.bridge.connect();
      })
      .catch((error) => {
        this.logLine("error", `the renderer core failed to load: ${error?.stack || error}`);
        this.showConsole(true);
      });
  }

  // -- preferences --------------------------------------------------------

  loadPrefs() {
    try {
      return JSON.parse(localStorage.getItem("pn-preview") || "{}");
    } catch (err) {
      return {};
    }
  }

  savePrefs() {
    try {
      localStorage.setItem(
        "pn-preview",
        JSON.stringify({
          device: this.device.id,
          landscape: this.landscape,
          scheme: this.scheme,
          consoleOpen: !this.consoleEl.classList.contains("pn-hidden"),
          consoleHeight: this.consoleHeight || undefined,
        }),
      );
    } catch (err) {
      /* ignore */
    }
  }

  // -- geometry -------------------------------------------------------------

  /** Whether the frame is drawn rotated (the fill-window "device" has no orientation). */
  isLandscape() {
    return this.landscape && !!this.device.width;
  }

  /**
   * The window the app sees: its size in points and the safe-area insets.
   * `top` is the status bar height the host reserves above the content.
   */
  frameMetrics() {
    const device = this.device;
    let width = device.width;
    let height = device.height;
    if (!width || !height) {
      const rect = this.stage.getBoundingClientRect();
      width = Math.max(320, Math.floor(rect.width) - 32);
      height = Math.max(480, Math.floor(rect.height) - 32);
    } else if (this.isLandscape()) {
      [width, height] = [height, width];
    }
    const insets = this.isLandscape() ? device.landscape : { top: device.top, left: 0, right: 0, bottom: device.bottom };
    return {
      width,
      height,
      top: insets.top,
      bottomInset: insets.bottom,
      leftInset: insets.left,
      rightInset: insets.right,
    };
  }

  /** The device's bezels as [top, right, bottom, left], turned with the device. */
  bezels() {
    const [top, right, bottom, left] = this.device.bezel;
    // Rotated a quarter turn counterclockwise: the portrait top becomes the left edge.
    return this.isLandscape() ? [right, bottom, left, top] : [top, right, bottom, left];
  }

  applyDevice() {
    const device = this.device;
    const metrics = this.frameMetrics();
    const flat = !device.width;
    const landscape = this.isLandscape();
    const frame = this.frame;
    frame.classList.toggle("pn-frame-flat", flat);
    frame.classList.toggle("pn-landscape", landscape);
    frame.dataset.chrome = device.chrome;
    frame.dataset.platform = device.platform;
    const [bt, br, bb, bl] = this.bezels();
    const style = frame.style;
    style.setProperty("--pn-bt", px(bt));
    style.setProperty("--pn-br", px(br));
    style.setProperty("--pn-bb", px(bb));
    style.setProperty("--pn-bl", px(bl));
    style.setProperty("--pn-frame-radius", px(device.radius[0]));
    style.setProperty("--pn-screen-radius", px(device.radius[1]));
    // The status bar band: around the Dynamic Island on an iPhone, the full bar elsewhere.
    const island = device.chrome === "island";
    style.setProperty("--pn-top", px(metrics.top));
    // Navigation bars keep their buttons clear of a landscape iPhone's sensor housing.
    style.setProperty("--pn-safe-left", px(metrics.leftInset));
    style.setProperty("--pn-safe-right", px(metrics.rightInset));
    style.setProperty("--pn-sb-pad", px(island ? 11 : 0));
    style.setProperty("--pn-sb-row", px(island ? 37 : metrics.top));
    style.width = px(metrics.width);
    style.height = px(metrics.height);
    for (const el of [this.screens, this.overlays]) {
      el.style.width = px(metrics.width);
      el.style.height = px(metrics.height);
    }
    const home = device.chrome === "home-button" ? "pn-home-button"
      : device.platform === "android" ? "pn-home-gesture"
      : metrics.bottomInset ? "pn-home-indicator" : "";
    this.home.className = `pn-home ${home}`.trim();
    $("pn-rotate").disabled = flat;
    this.tickClock?.();
    this.applyStatusBar();
    this.fitFrame();
    this.host.relayout();
  }

  /** Scale the frame down (never up) so the whole device fits the stage. */
  fitFrame() {
    const metrics = this.frameMetrics();
    if (!this.device.width) {
      // The fill-window frame tracks the stage itself.
      const width = parseFloat(this.frame.style.width);
      const height = parseFloat(this.frame.style.height);
      if (width !== metrics.width || height !== metrics.height) {
        this.applyDevice();
        return;
      }
    }
    const [bt, br, bb, bl] = this.bezels();
    const stage = this.stage.getBoundingClientRect();
    const available = { w: stage.width - 32, h: stage.height - 32 };
    const total = { w: metrics.width + bl + br, h: metrics.height + bt + bb };
    this.scale = Math.max(0.1, Math.min(1, available.w / total.w, available.h / total.h));
    this.frame.style.transform = this.scale === 1 ? "" : `scale(${this.scale})`;
    $("pn-dims").textContent = `${metrics.width}×${metrics.height}${this.scale < 1 ? ` · ${Math.round(this.scale * 100)}%` : ""}`;
  }

  applyScheme() {
    const dark = this.scheme === "dark";
    document.body.classList.toggle("pn-dark-shell", dark);
    this.frame.classList.toggle("pn-dark", dark);
    const button = $("pn-scheme");
    button.setAttribute("aria-label", `Switch to ${dark ? "light" : "dark"} appearance`);
    button.querySelector(".pn-tb-label").textContent = dark ? "Light" : "Dark";
    this.applyStatusBar();
  }

  applyStatusBar() {
    const st = this.statusBarState;
    // A landscape iPhone has no status bar at all.
    this.statusbar.classList.toggle("pn-hidden-bar", st.hidden || this.frameMetrics().top === 0);
    const light = st.light || (!st.dark && this.scheme === "dark");
    this.statusbar.classList.toggle("pn-light-content", light);
  }

  startClock() {
    const tick = () => {
      const now = new Date();
      const time = `${now.getHours() % 12 || 12}:${String(now.getMinutes()).padStart(2, "0")}`;
      // iPadOS shows the date beside the time.
      $("pn-clock").textContent = this.device.chrome === "tablet"
        ? `${time} ${now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }).replace(/,/g, "")}`
        : time;
    };
    this.tickClock = tick;
    tick();
    setInterval(tick, 15000);
  }

  // -- renderer context -------------------------------------------------------

  rendererContext() {
    return {
      scheme: () => this.scheme,
      nativeStackChanged: () => this.host?.nativeStackChanged(),
      overlays: () => this.overlays,
      bottomInset: () => this.frameMetrics().bottomInset,
      frameWidth: () => this.frameMetrics().width,
      pointInFrame: (event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        return { x: (event.clientX - rect.left) / this.scale, y: (event.clientY - rect.top) / this.scale };
      },
      // Window coordinates for `absolute_x` / `absolute_y`: the device frame is the app window.
      pointInWindow: (event) => {
        const rect = this.screens.getBoundingClientRect();
        return { x: (event.clientX - rect.left) / this.scale, y: (event.clientY - rect.top) / this.scale };
      },
      // An element's laid-out origin in window points (transforms, such as a
      // screen sliding in, don't count): what a container reports to the core.
      windowOrigin: (el) => {
        let x = 0;
        let y = 0;
        for (let node = el; node && node !== this.screens && node !== this.overlays; node = node.offsetParent) {
          x += node.offsetLeft - (node === el ? 0 : node.scrollLeft);
          y += node.offsetTop - (node === el ? 0 : node.scrollTop);
          if (node.offsetParent === null) break;
        }
        return { x, y };
      },
      statusBar: (opts) => {
        this.statusBarState = { ...this.statusBarState, ...opts };
        this.applyStatusBar();
        this.host.statusBarHidden = !!opts.hidden;
        this.host.relayout();
      },
    };
  }

  // -- bridge -----------------------------------------------------------------

  installBridgeHandlers() {
    const b = this.bridge;
    // Python's calls into the core (`pythonnative.bridge.web.WebTransport`):
    // JSON text in, the core's JSON text out.
    b.handlers.load_contracts = (message) => this.core.loadContracts(message[2]);
    b.handlers.commit = (message) => this.core.commit(message[2]);
    b.handlers.layout = (message) => this.core.layout(message[2]);
    b.handlers.command = (message) => this.core.command(message[2], message[3], message[4], message[5], message[6]);
    b.handlers.animate = (message) => this.core.animate(message[2], message[3], message[4]);
    b.handlers.measure = (message) => this.core.measure(message[2], message[3]);
    b.handlers.call = (message) => this.host.call(message[2], message[3], message[4]);

    b.onOpen = () => {
      this.setConnected(true);
      this.bridge.dev({
        type: "hello",
        user_agent: navigator.userAgent,
        device: this.device.id,
        width: this.frameMetrics().width,
        height: this.frameMetrics().height,
        color_scheme: this.scheme,
      });
    };
    b.onClose = (wasConnected) => {
      this.setConnected(false);
      if (wasConnected) {
        this.host.clear();
        // The next session compiles its contracts and mounts on a fresh core.
        this.core.reset();
        this.logLine("info", "disconnected from pn start; retrying...");
      } else {
        this.explainRefusal();
      }
    };
    b.onDev = (payload) => this.onDevMessage(payload);
    window.addEventListener("error", (event) => {
      this.logLine("error", `page error: ${event.message}`);
    });
    window.addEventListener("unhandledrejection", (event) => {
      this.logLine("error", `unhandled rejection: ${event.reason}`);
    });
  }

  // The page is public, but the socket needs the dev token, which the page
  // holds as a cookie once it has been opened through the URL `pn start`
  // printed. Browsers hide why a WebSocket upgrade failed, so ask `/status`.
  async explainRefusal() {
    try {
      const response = await fetch("/status", { cache: "no-store" });
      if (response.status === 401 || response.status === 403) {
        this.connect.classList.add("pn-connect-refused");
        $("pn-connect-title").textContent = "This page needs the dev token";
        const detail = $("pn-connect-detail");
        detail.textContent = "";
        const url = document.createElement("code");
        url.textContent = "?token=";
        const command = document.createElement("code");
        command.textContent = "pn start";
        detail.append("Open the preview URL that ", command, " printed; it ends in ", url, ".");
      }
    } catch (err) {
      /* the server is down; the default message applies */
    }
  }

  setConnected(connected) {
    const dot = $("pn-status-dot");
    dot.classList.toggle("pn-connected", connected);
    dot.title = connected ? "Connected to pn start" : "Disconnected";
    dot.setAttribute("aria-label", dot.title);
    this.connect.classList.toggle("pn-hidden", connected);
    if (connected) this.connect.classList.remove("pn-connect-refused");
    if (!connected) {
      $("pn-connect-title").innerHTML = "Waiting for <code>pn start</code>";
      $("pn-connect-detail").textContent = "Lost the dev server. Waiting for it to come back...";
    }
  }

  async onDevMessage(payload) {
    switch (payload.type) {
      case "hello": {
        this.project = payload.project || "";
        $("pn-project-name").textContent = this.project;
        document.title = `${this.project || "PythonNative"} preview`;
        this.entry = payload.entry || null;
        // Python remounts under a new application id; the core's first
        // commit for it resets the surface's views.
        await assets.ready;
        await this.host.start(this.entry);
        this.logLine("ok", `mounted ${this.entry}`);
        break;
      }
      case "remount":
        await this.host.start(this.entry);
        break;
      case "log":
        this.logLine(payload.level || "info", payload.text || "");
        break;
      case "error":
        this.logLine("error", payload.text || "");
        this.toast(payload.text || "error", "error", 6000);
        this.showConsole(true);
        break;
      case "reload": {
        const modules = Array.isArray(payload.modules) ? payload.modules : [];
        if (payload.ok === false) {
          const text = payload.error || "Reload failed";
          this.toast(text, "error", 8000);
          this.logLine("error", text);
          this.showConsole(true);
        } else {
          const label = payload.mode === "fast_refresh" ? "Fast Refresh" : "Remounted";
          const ms = payload.ms != null ? ` in ${Math.round(payload.ms)} ms` : "";
          this.toast(`${label}: ${modules.join(", ")}${ms}`, "ok", 1500);
          this.logLine("ok", `${label.toLowerCase()}: ${modules.join(", ")}${ms}`);
        }
        break;
      }
      case "assets":
        await assets.refresh();
        this.logLine("ok", "assets refreshed");
        break;
      case "superseded":
        this.bridge.close();
        this.setConnected(false);
        this.connect.classList.add("pn-connect-refused");
        $("pn-connect-title").textContent = "Another preview tab took over";
        $("pn-connect-detail").textContent = "Close this one, or reload it to take back control.";
        break;
      default:
        break;
    }
  }

  // -- toolbar --------------------------------------------------------------

  installToolbar() {
    const select = $("pn-device");
    for (const [label, platform] of DEVICE_GROUPS) {
      const group = document.createElement("optgroup");
      group.label = label;
      for (const device of DEVICES) {
        if ((device.chrome === "none" ? null : device.platform) !== platform) continue;
        const option = document.createElement("option");
        option.value = device.id;
        option.textContent = device.name;
        option.selected = device.id === this.device.id;
        group.appendChild(option);
      }
      select.appendChild(group);
    }
    select.addEventListener("change", () => {
      this.device = DEVICES.find((d) => d.id === select.value) || DEVICES[0];
      this.savePrefs();
      this.applyDevice();
    });
    $("pn-rotate").addEventListener("click", () => this.rotate());
    $("pn-scheme").addEventListener("click", () => this.toggleScheme());
    $("pn-back").addEventListener("click", () => this.host.backPressed());
    $("pn-reload").addEventListener("click", () => this.remount());
    $("pn-console-toggle").addEventListener("click", () => this.toggleConsole());
    $("pn-dev-menu").addEventListener("click", () => this.host.devSupport.requestMenu());
    document.addEventListener("keydown", (event) => {
      // Cmd+D (Ctrl+D elsewhere) opens the dev menu, as in the iOS Simulator.
      if ((event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "d") {
        event.preventDefault();
        this.host.devSupport.requestMenu();
        return;
      }
      const target = event.target;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT")) {
        if (event.key !== "Escape") return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "r") this.rotate();
      else if (event.key === "R" && event.shiftKey) this.remount();
      else if (event.key === "d") this.toggleScheme();
      else if (event.key === "Escape") this.host.backPressed();
      else if (event.key === "`") this.toggleConsole();
      else return;
      event.preventDefault();
    });
  }

  rotate() {
    this.landscape = !this.landscape;
    this.savePrefs();
    this.applyDevice();
  }

  toggleScheme() {
    this.scheme = this.scheme === "dark" ? "light" : "dark";
    this.savePrefs();
    this.applyScheme();
    this.renderer.refreshColors();
    this.host.appearanceChanged();
  }

  remount() {
    this.bridge.dev({ type: "remount" });
  }

  // -- console / toasts ---------------------------------------------------------

  installConsole() {
    $("pn-console-clear").addEventListener("click", () => {
      this.consoleLines.textContent = "";
      this.setUnread(0);
    });
    $("pn-console-close").addEventListener("click", () => this.showConsole(false));
    if (this.consoleHeight) this.consoleEl.style.setProperty("--pn-console-height", px(this.consoleHeight));
    // Drag the console's title bar to resize it.
    const bar = this.consoleEl.querySelector(".pn-console-bar");
    bar.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("button")) return;
      event.preventDefault();
      bar.setPointerCapture(event.pointerId);
      const startY = event.clientY;
      const startHeight = this.consoleEl.getBoundingClientRect().height;
      const move = (moved) => {
        const height = Math.round(Math.min(window.innerHeight * 0.7, Math.max(90, startHeight + startY - moved.clientY)));
        this.consoleHeight = height;
        this.consoleEl.style.setProperty("--pn-console-height", px(height));
      };
      const end = () => {
        bar.removeEventListener("pointermove", move);
        this.savePrefs();
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", end, { once: true });
      bar.addEventListener("pointercancel", end, { once: true });
    });
    if (this.loadPrefs().consoleOpen) this.showConsole(true, { save: false });
  }

  toggleConsole() {
    this.showConsole(this.consoleEl.classList.contains("pn-hidden"));
  }

  showConsole(open, { save = true } = {}) {
    this.consoleEl.classList.toggle("pn-hidden", !open);
    $("pn-console-toggle").setAttribute("aria-pressed", String(open));
    if (open) {
      this.setUnread(0);
      this.consoleLines.scrollTop = this.consoleLines.scrollHeight;
    }
    if (save) this.savePrefs();
  }

  /** The count of errors logged while the console was closed, shown on its button. */
  setUnread(count) {
    this.unreadErrors = count;
    const badge = $("pn-console-badge");
    badge.hidden = count === 0;
    badge.textContent = count > 99 ? "99+" : String(count);
  }

  logLine(level, text) {
    const line = document.createElement("div");
    const kind = level === "warning" ? "warn" : level;
    if (["error", "warn", "ok", "info"].includes(kind)) line.className = `pn-line-${kind}`;
    const stamp = document.createElement("span");
    stamp.className = "pn-stamp";
    stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
    line.append(stamp, String(text));
    const lines = this.consoleLines;
    // Follow new output only while the reader is already at the bottom.
    const pinned = lines.scrollHeight - lines.scrollTop - lines.clientHeight < 24;
    lines.appendChild(line);
    while (lines.childElementCount > 500) lines.firstChild.remove();
    if (pinned) lines.scrollTop = lines.scrollHeight;
    if (kind === "error" && this.consoleEl.classList.contains("pn-hidden")) this.setUnread(this.unreadErrors + 1);
  }

  toast(text, kind = "info", duration = 2000) {
    const el = document.createElement("div");
    el.className = `pn-toast pn-toast-${kind}`;
    el.textContent = text;
    // Keep the stack short: a burst of saves shouldn't bury the frame.
    while (this.toasts.childElementCount >= 3) this.toasts.firstChild.remove();
    this.toasts.appendChild(el);
    const dismiss = () => {
      if (!el.isConnected || el.classList.contains("pn-toast-leaving")) return;
      el.classList.add("pn-toast-leaving");
      setTimeout(() => el.remove(), 200);
    };
    if (kind === "error") {
      el.title = "Click to dismiss";
      el.addEventListener("click", dismiss);
    }
    setTimeout(dismiss, duration);
  }
}

window.pnPreview = new Shell();
