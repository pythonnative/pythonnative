// Entry point for the browser preview: wires the bridge, the DOM
// renderer, and the screen host together and drives the toolbar.

import { Bridge } from "./bridge.js";
import { Renderer } from "./renderer.js";
import { PreviewHost } from "./host.js";
import { color as parseColor } from "./colors.js";

const DEVICES = [
  { id: "iphone-15", name: "iPhone 15", width: 393, height: 852, bottom: 34, notch: true },
  { id: "iphone-15-pro-max", name: "iPhone 15 Pro Max", width: 430, height: 932, bottom: 34, notch: true },
  { id: "iphone-se", name: "iPhone SE", width: 375, height: 667, bottom: 0, notch: false },
  { id: "pixel-8", name: "Pixel 8", width: 412, height: 915, bottom: 24, notch: true },
  { id: "pixel-fold", name: "Pixel Fold (inner)", width: 841, height: 701, bottom: 24, notch: true },
  { id: "ipad-mini", name: "iPad mini", width: 744, height: 1133, bottom: 20, notch: false },
  { id: "responsive", name: "Fill window", width: 0, height: 0, bottom: 0, notch: false },
];

const $ = (id) => document.getElementById(id);

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

    const saved = this.loadPrefs();
    this.device = DEVICES.find((d) => d.id === saved.device) || DEVICES[0];
    this.landscape = !!saved.landscape;
    this.scheme = saved.scheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
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
      scheme: () => this.scheme,
      color: (value) => parseColor(value, this.scheme),
      log: (level, text) => this.logLine(level, text),
      toast: (text, kind) => this.toast(text, kind),
    });

    this.installBridgeHandlers();
    this.installToolbar();
    this.applyDevice();
    this.applyScheme();
    this.startClock();
    window.addEventListener("resize", () => this.applyDevice());
    this.bridge.connect();
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
        JSON.stringify({ device: this.device.id, landscape: this.landscape, scheme: this.scheme }),
      );
    } catch (err) {
      /* ignore */
    }
  }

  // -- geometry -------------------------------------------------------------

  frameMetrics() {
    let width = this.device.width;
    let height = this.device.height;
    if (!width || !height) {
      const rect = this.stage.getBoundingClientRect();
      width = Math.max(320, Math.floor(rect.width) - 32);
      height = Math.max(480, Math.floor(rect.height) - 32);
    } else if (this.landscape) {
      [width, height] = [height, width];
    }
    return { width, height, bottomInset: this.landscape ? 0 : this.device.bottom };
  }

  applyDevice() {
    const { width, height } = this.frameMetrics();
    const flat = !this.device.width || !this.device.notch;
    this.frame.classList.toggle("pn-frame-flat", flat);
    const bezel = flat ? 0 : 12;
    this.frame.style.width = `${width}px`;
    this.frame.style.height = `${height}px`;
    for (const el of [this.screens, this.overlays]) {
      el.style.width = `${width}px`;
      el.style.height = `${height}px`;
    }
    this.home.style.display = this.device.bottom && !this.landscape ? "" : "none";
    const stage = this.stage.getBoundingClientRect();
    const available = { w: stage.width - 32, h: stage.height - 32 };
    const total = { w: width + bezel * 2, h: height + bezel * 2 };
    this.scale = Math.min(1, available.w / total.w, available.h / total.h);
    this.frame.style.transform = `scale(${this.scale})`;
    this.host.relayout();
  }

  applyScheme() {
    document.body.classList.toggle("pn-dark-shell", this.scheme === "dark");
    this.frame.classList.toggle("pn-dark", this.scheme === "dark");
    $("pn-scheme").textContent = this.scheme === "dark" ? "Light" : "Dark";
    this.applyStatusBar();
  }

  applyStatusBar() {
    const st = this.statusBarState;
    this.statusbar.classList.toggle("pn-hidden-bar", st.hidden);
    const light = st.light || (!st.dark && this.scheme === "dark");
    this.statusbar.classList.toggle("pn-light-content", light);
  }

  startClock() {
    const tick = () => {
      const now = new Date();
      $("pn-clock").textContent = `${now.getHours() % 12 || 12}:${String(now.getMinutes()).padStart(2, "0")}`;
    };
    tick();
    setInterval(tick, 15000);
  }

  // -- renderer context -------------------------------------------------------

  rendererContext() {
    return {
      emit: (tag, name, args) => this.bridge.callback("event", tag, name, JSON.stringify(args ?? [])),
      request: (tag, name, args) => this.bridge.request("event", tag, name, JSON.stringify(args ?? [])),
      gesture: (tag, phase, info) => this.bridge.send(["gesture", tag, phase, info]),
      animationFinished: (id, finished) => this.bridge.callback("animation", 0, "", JSON.stringify({ id, finished })),
      scheme: () => this.scheme,
      overlays: () => this.overlays,
      bottomInset: () => this.frameMetrics().bottomInset,
      frameWidth: () => this.frameMetrics().width,
      pointInFrame: (event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        return { x: (event.clientX - rect.left) / this.scale, y: (event.clientY - rect.top) / this.scale };
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
    b.handlers.apply = (message) => this.renderer.apply(message[1]);
    b.handlers.measure = (message) => this.renderer.measure(message[2], message[3], message[4]);
    b.handlers.command = (message) => this.renderer.command(message[2], message[3], message[4]);
    b.handlers.animate = (message) => this.renderer.animate(message[2], message[3]);
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
        this.renderer.reset();
        this.logLine("info", "disconnected from pn start; retrying...");
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

  setConnected(connected) {
    $("pn-status-dot").classList.toggle("pn-connected", connected);
    $("pn-status-dot").title = connected ? "Connected" : "Disconnected";
    this.connect.classList.toggle("pn-hidden", connected);
    if (!connected) $("pn-connect-detail").textContent = "Lost the dev server. Waiting for it to come back...";
  }

  async onDevMessage(payload) {
    switch (payload.type) {
      case "hello": {
        this.project = payload.project || "";
        $("pn-project-name").textContent = this.project ? `· ${this.project}` : "";
        document.title = `${this.project || "PythonNative"} preview`;
        this.entry = payload.entry || null;
        this.renderer.reset();
        await this.host.start(this.entry);
        this.logLine("ok", `mounted ${this.entry}`);
        break;
      }
      case "remount":
        this.renderer.reset();
        await this.host.start(this.entry);
        break;
      case "log":
        this.logLine(payload.level || "info", payload.text || "");
        break;
      case "error":
        this.logLine("error", payload.text || "");
        this.toast(payload.text || "error", "error", 6000);
        this.consoleEl.classList.remove("pn-hidden");
        break;
      case "reload": {
        const modules = Array.isArray(payload.modules) ? payload.modules : [];
        if (payload.ok === false) {
          const text = payload.error || "Reload failed";
          this.toast(text, "error", 8000);
          this.logLine("error", text);
          this.consoleEl.classList.remove("pn-hidden");
        } else {
          const label = payload.mode === "fast_refresh" ? "Fast Refresh" : "Remounted";
          const ms = payload.ms != null ? ` in ${Math.round(payload.ms)} ms` : "";
          this.toast(`${label}: ${modules.join(", ")}${ms}`, "ok", 1500);
          this.logLine("ok", `${label.toLowerCase()}: ${modules.join(", ")}${ms}`);
        }
        break;
      }
      case "superseded":
        this.bridge.close();
        this.setConnected(false);
        $("pn-connect-detail").textContent = "Another preview tab took over. Close this one or reload it to take back control.";
        break;
      default:
        break;
    }
  }

  // -- toolbar --------------------------------------------------------------

  installToolbar() {
    const select = $("pn-device");
    for (const device of DEVICES) {
      const option = document.createElement("option");
      option.value = device.id;
      option.textContent = device.name;
      option.selected = device.id === this.device.id;
      select.appendChild(option);
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
    $("pn-console-toggle").addEventListener("click", () => this.consoleEl.classList.toggle("pn-hidden"));
    $("pn-console-clear").addEventListener("click", () => (this.consoleLines.textContent = ""));
    document.addEventListener("keydown", (event) => {
      const target = event.target;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT")) {
        if (event.key !== "Escape") return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "r") this.rotate();
      else if (event.key === "R" && event.shiftKey) this.remount();
      else if (event.key === "d") this.toggleScheme();
      else if (event.key === "Escape") this.host.backPressed();
      else if (event.key === "`") this.consoleEl.classList.toggle("pn-hidden");
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

  logLine(level, text) {
    const line = document.createElement("div");
    line.className = level === "error" ? "pn-line-error" : level === "ok" ? "pn-line-ok" : level === "info" ? "pn-line-info" : "";
    const stamp = new Date().toLocaleTimeString([], { hour12: false });
    line.textContent = `${stamp}  ${text}`;
    this.consoleLines.appendChild(line);
    while (this.consoleLines.childElementCount > 500) this.consoleLines.firstChild.remove();
    this.consoleLines.scrollTop = this.consoleLines.scrollHeight;
  }

  toast(text, kind = "info", duration = 2000) {
    const el = document.createElement("div");
    el.className = `pn-toast pn-toast-${kind}`;
    el.textContent = text;
    this.toasts.appendChild(el);
    if (kind === "error") el.addEventListener("click", () => el.remove());
    setTimeout(() => el.remove(), duration);
  }
}

window.pnPreview = new Shell();
