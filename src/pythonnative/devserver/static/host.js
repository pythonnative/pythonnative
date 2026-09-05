// The page's `Host` module and screen stack, plus the other native
// modules the browser can honor (Alert, Clipboard, Linking, Share,
// Haptics, NetInfo, AppState, Device).
//
// A "screen" here is what PNViewController is on iOS: it owns one
// Python screen id, sends host lifecycle events (`create`, `start`,
// `layout`, `resume`, `pause`, `stop`, `destroy`), and hosts the root
// view Python attaches with `Host.attach_root`. Screens stack inside the
// phone frame with a slide transition; a header with a back button
// stands in for UINavigationBar.

const STATUS_BAR = 47;
const HEADER = 44;

export class Screen {
  constructor(host, id, path, argsJson, options) {
    this.host = host;
    this.id = id;
    this.path = path;
    this.argsJson = argsJson;
    this.options = { header_shown: true, ...(options || {}) };
    this.root = null;
    this.created = false;
    this.lastLayout = "";

    this.el = document.createElement("section");
    this.el.className = "pn-screen";
    this.el.dataset.screen = String(id);
    this.header = document.createElement("div");
    this.header.className = "pn-header";
    this.back = document.createElement("button");
    this.back.className = "pn-back";
    this.back.textContent = "Back";
    this.back.addEventListener("click", () => host.backPressed());
    this.title = document.createElement("span");
    this.title.className = "pn-title";
    this.header.appendChild(this.back);
    this.header.appendChild(this.title);
    this.content = document.createElement("div");
    this.content.className = "pn-content";
    this.el.appendChild(this.header);
    this.el.appendChild(this.content);
  }

  applyOptions(options) {
    Object.assign(this.options, options || {});
    const o = this.options;
    this.title.textContent = o.title == null ? "" : String(o.title);
    this.header.style.display = o.header_shown === false ? "none" : "";
    this.back.style.visibility = this.host.stack.indexOf(this) > 0 && !o.hide_back_button ? "" : "hidden";
    const tint = this.host.color(o.header_tint_color);
    this.back.style.color = tint ?? "";
    const bg = this.host.color(o.header_background_color);
    this.header.style.background = bg ?? "";
    this.layout();
  }

  /** Top offset of the content area (status bar + header when shown). */
  contentTop() {
    const bar = this.host.statusBarHidden ? 0 : STATUS_BAR;
    return bar + (this.options.header_shown === false ? 0 : HEADER);
  }

  viewport() {
    const { width, height, bottomInset } = this.host.frameMetrics();
    const top = this.contentTop();
    return {
      width,
      height: Math.max(0, height - top),
      insets: { top: 0, left: 0, bottom: bottomInset, right: 0 },
      keyboard_height: 0,
      color_scheme: this.host.scheme(),
    };
  }

  layout() {
    const top = this.contentTop();
    this.header.style.top = `${this.host.statusBarHidden ? 0 : STATUS_BAR}px`;
    this.content.style.top = `${top}px`;
    if (!this.created) return;
    const payload = JSON.stringify(this.viewport());
    if (payload !== this.lastLayout) {
      this.lastLayout = payload;
      this.host.hostEvent(this.id, "layout", payload);
    }
  }

  attachRoot(view) {
    this.root = view;
    this.content.appendChild(view.el);
    view.el.classList.add("pn-root");
  }

  detachRoot(view) {
    if (this.root === view) this.root = null;
    if (view.el.parentNode === this.content) this.content.removeChild(view.el);
  }
}

export class PreviewHost {
  /**
   * @param opts {{
   *   bridge, renderer, screensEl, overlaysEl, frameMetrics(), scheme(),
   *   color(value), statusBar(opts), log(level, text)
   * }}
   */
  constructor(opts) {
    Object.assign(this, opts);
    this.stack = [];
    this.nextScreenId = 1;
    this.statusBarHidden = false;
    this.appState = "active";
    this.entry = null;
    this.installVisibilityTracking();
    this.installNetworkTracking();
  }

  // -- lifecycle ---------------------------------------------------------

  /** Mount the entry screen (or remount after a reset). */
  async start(entry) {
    this.entry = entry || this.entry;
    await this.clear();
    await this.pushScreen(this.entry, null, {}, { animated: false });
  }

  async clear() {
    for (const screen of [...this.stack].reverse()) {
      this.hostEvent(screen.id, "pause", "{}");
      this.hostEvent(screen.id, "stop", "{}");
      this.hostEvent(screen.id, "destroy", "{}");
      screen.el.remove();
    }
    this.stack = [];
    this.overlaysEl.textContent = "";
  }

  async pushScreen(path, argsJson, options, { animated = true } = {}) {
    const screen = new Screen(this, this.nextScreenId++, path, argsJson, options);
    const previous = this.top();
    if (previous) this.hostEvent(previous.id, "pause", "{}");
    this.stack.push(screen);
    this.screensEl.appendChild(screen.el);
    if (animated) screen.el.classList.add("pn-enter");
    screen.applyOptions({});
    const payload = { path: path || null, args: argsJson ?? null, ...screen.viewport() };
    const reply = await this.bridge.request("host", screen.id, "create", JSON.stringify(payload));
    screen.created = true;
    screen.lastLayout = JSON.stringify(screen.viewport());
    this.attachFromReply(screen, reply);
    this.hostEvent(screen.id, "start", "{}");
    if (animated) {
      requestAnimationFrame(() => screen.el.classList.remove("pn-enter"));
      if (previous) previous.el.classList.add("pn-under");
    }
    this.hostEvent(screen.id, "resume", JSON.stringify(screen.viewport()));
    if (previous) this.hostEvent(previous.id, "stop", "{}");
    return screen;
  }

  attachFromReply(screen, reply) {
    let root = null;
    try {
      const parsed = typeof reply === "string" ? JSON.parse(reply) : reply;
      root = parsed && parsed.root != null ? Number(parsed.root) : null;
    } catch (err) {
      root = null;
    }
    if (root == null || screen.root) return;
    const view = this.renderer.views.get(root);
    if (view) screen.attachRoot(view);
  }

  popScreens(count = 1) {
    if (this.stack.length <= 1) return false;
    const removed = [];
    for (let i = 0; i < count && this.stack.length > 1; i++) removed.push(this.stack.pop());
    const revealed = this.top();
    for (const screen of removed) {
      this.hostEvent(screen.id, "pause", "{}");
      screen.el.classList.add("pn-enter");
      setTimeout(() => {
        screen.el.remove();
        this.hostEvent(screen.id, "stop", "{}");
        this.hostEvent(screen.id, "destroy", "{}");
      }, 280);
    }
    revealed.el.classList.remove("pn-under");
    revealed.applyOptions({});
    this.hostEvent(revealed.id, "start", "{}");
    this.hostEvent(revealed.id, "resume", JSON.stringify(revealed.viewport()));
    return true;
  }

  async replaceScreen(target, path, argsJson, options) {
    const index = this.stack.indexOf(target);
    if (index < 0) return false;
    if (index === this.stack.length - 1) {
      // Replace the visible screen: push the new one, then drop the old one under it.
      const next = await this.pushScreen(path, argsJson, options, { animated: true });
      this.stack.splice(index, 1);
      target.el.remove();
      this.hostEvent(target.id, "stop", "{}");
      this.hostEvent(target.id, "destroy", "{}");
      next.applyOptions({});
      return true;
    }
    const screen = new Screen(this, this.nextScreenId++, path, argsJson, options);
    this.stack[index] = screen;
    this.screensEl.insertBefore(screen.el, target.el);
    screen.el.classList.add("pn-under");
    target.el.remove();
    this.hostEvent(target.id, "destroy", "{}");
    const payload = { path: path || null, args: argsJson ?? null, ...screen.viewport() };
    const reply = await this.bridge.request("host", screen.id, "create", JSON.stringify(payload));
    screen.created = true;
    this.attachFromReply(screen, reply);
    return true;
  }

  top() {
    return this.stack[this.stack.length - 1] || null;
  }

  async backPressed() {
    const screen = this.top();
    if (!screen) return;
    const reply = await this.bridge.request("host", screen.id, "back_pressed", "{}");
    if (reply === "true" || reply === true) return;
    this.popScreens(1);
  }

  hostEvent(screenId, name, payload) {
    this.bridge.callback("host", screenId, name, payload);
  }

  /** Re-run layout for every screen (rotation, device change, scheme change). */
  relayout() {
    for (const screen of this.stack) screen.layout();
  }

  appearanceChanged() {
    this.bridge.callback("host", 0, "appearance", JSON.stringify({ color_scheme: this.scheme() }));
    this.relayout();
  }

  screenById(id) {
    return this.stack.find((s) => s.id === Number(id)) || null;
  }

  // -- native modules ----------------------------------------------------

  /** Handle `["call", id, module, method, envelopeJson]`; returns the JSON result text. */
  async call(module, method, envelopeJson) {
    let envelope = {};
    try {
      envelope = envelopeJson ? JSON.parse(envelopeJson) || {} : {};
    } catch (err) {
      envelope = {};
    }
    const args = envelope.args || {};
    const callId = Number(envelope.call_id) || 0;
    const impl = this.modules()[module];
    if (!impl) return JSON.stringify({ ok: false, error: `no browser module named ${module}`, code: "unknown_module" });
    const fn = impl[method];
    if (typeof fn !== "function") {
      return JSON.stringify({ ok: false, error: `${module} has no method '${method}'`, code: "unknown_method" });
    }
    let result;
    try {
      result = fn.call(impl, args);
    } catch (err) {
      return JSON.stringify({ ok: false, error: String(err && err.message ? err.message : err) });
    }
    if (result && typeof result.then === "function") {
      if (callId === 0) {
        // Synchronous call of an async method: wait for it (the request
        // path is already asynchronous on this side).
        try {
          return JSON.stringify({ ok: true, value: nullish(await result) });
        } catch (err) {
          return JSON.stringify({ ok: false, error: String(err && err.message ? err.message : err) });
        }
      }
      result
        .then((value) => this.moduleMessage(module, { call_id: callId, ok: true, value: nullish(value) }))
        .catch((err) => this.moduleMessage(module, { call_id: callId, ok: false, error: String(err && err.message ? err.message : err) }));
      return JSON.stringify({ pending: true });
    }
    return JSON.stringify({ ok: true, value: nullish(result) });
  }

  moduleMessage(module, message) {
    this.bridge.callback("module", 0, module, JSON.stringify(message));
  }

  moduleEvent(module, event, payload) {
    this.moduleMessage(module, { event, payload });
  }

  modules() {
    if (this._modules) return this._modules;
    const host = this;
    this._modules = {
      Host: {
        post() {
          return null;
        },
        is_main_thread() {
          return true;
        },
        attach_root({ screen, tag }) {
          const s = host.screenById(screen);
          const view = host.renderer.views.get(Number(tag));
          if (!s || !view) throw new Error("attach_root: unknown screen or view");
          s.attachRoot(view);
          return s.viewport();
        },
        detach_root({ screen, tag }) {
          const s = host.screenById(screen);
          const view = host.renderer.views.get(Number(tag));
          if (s && view) s.detachRoot(view);
          return null;
        },
        viewport({ screen }) {
          const s = host.screenById(screen);
          return s ? s.viewport() : new Screen(host, 0, null, null, {}).viewport();
        },
        set_options({ screen, options }) {
          const s = host.screenById(screen);
          if (s) s.applyOptions(options || {});
          return null;
        },
        push({ path, args, options }) {
          host.pushScreen(path, args ?? null, options || {});
          return true;
        },
        pop({ count }) {
          return host.popScreens(Math.max(1, Number(count) || 1));
        },
        pop_to_root() {
          return host.popScreens(host.stack.length - 1);
        },
        replace({ screen, path, args, options }) {
          const s = host.screenById(screen);
          if (!s) return false;
          host.replaceScreen(s, path, args ?? null, options || {});
          return true;
        },
        reset({ screens }) {
          (async () => {
            while (host.stack.length > 1) host.popScreens(1);
            for (const spec of Array.isArray(screens) ? screens : []) {
              await host.pushScreen(spec.path, spec.args ?? null, spec.options || {}, { animated: false });
            }
          })();
          return true;
        },
      },
      Alert: {
        show(args) {
          host.presentAlert(args);
          return null;
        },
        present(args) {
          return host.presentAlert(args);
        },
      },
      Clipboard: {
        async set_string({ text }) {
          host.clipboardText = text == null ? "" : String(text);
          try {
            await navigator.clipboard.writeText(host.clipboardText);
          } catch (err) {
            /* permission denied; keep the in-page copy */
          }
          return null;
        },
        async get_string() {
          try {
            return await navigator.clipboard.readText();
          } catch (err) {
            return host.clipboardText || "";
          }
        },
        has_string() {
          return !!host.clipboardText;
        },
      },
      Linking: {
        open_url({ url }) {
          const text = String(url || "");
          if (!text) return false;
          window.open(text, "_blank", "noopener");
          host.log("info", `Linking.open_url(${text})`);
          return true;
        },
        can_open_url({ url }) {
          return /^(https?|mailto|tel|sms):/i.test(String(url || ""));
        },
        get_initial_url() {
          return null;
        },
        open_settings() {
          host.log("info", "Linking.open_settings() has no browser equivalent");
          return false;
        },
      },
      Share: {
        async share({ message, url, title }) {
          if (navigator.share) {
            try {
              await navigator.share({ text: message || undefined, url: url || undefined, title: title || undefined });
              return true;
            } catch (err) {
              return false;
            }
          }
          host.log("info", `Share.share(${JSON.stringify({ message, url, title })})`);
          host.toast("Shared (see console)");
          return true;
        },
      },
      Haptics: {
        impact({ style }) {
          host.vibrate(style === "heavy" ? 30 : style === "light" ? 8 : 15);
          return null;
        },
        notification({ type_, type }) {
          host.vibrate((type_ || type) === "error" ? [30, 40, 30] : [12, 30, 12]);
          return null;
        },
        selection() {
          host.vibrate(5);
          return null;
        },
        vibrate({ duration_ms }) {
          host.vibrate(Number(duration_ms) || 50);
          return null;
        },
      },
      NetInfo: {
        fetch() {
          return host.netInfoSnapshot();
        },
      },
      AppState: {
        current_state() {
          return host.appState;
        },
      },
      Device: {
        info() {
          const [browser, version] = browserFamily(navigator.userAgent);
          return {
            platform: "web",
            os: browser,
            os_version: version,
            model: `${browser} on ${navigator.platform || "web"}`,
            app_dir: "~/.pythonnative_data",
            cache_dir: "~/.pythonnative_data/cache",
            temp_dir: "~/.pythonnative_data/tmp",
            locale: (navigator.language || "en-US").replace("-", "_"),
            app_version: "0.0.0",
            build_number: "0",
            bundle_id: "com.pythonnative.preview",
            screen_width: host.frameMetrics().width,
            screen_height: host.frameMetrics().height,
            scale: window.devicePixelRatio || 1,
            user_agent: navigator.userAgent,
          };
        },
      },
    };
    return this._modules;
  }

  // -- helpers -----------------------------------------------------------

  vibrate(pattern) {
    if (navigator.vibrate) navigator.vibrate(pattern);
  }

  netInfoSnapshot() {
    const online = navigator.onLine !== false;
    const conn = navigator.connection || {};
    return {
      is_connected: online,
      is_internet_reachable: online,
      type: online ? conn.type || "wifi" : "none",
      details: { effective_type: conn.effectiveType || null, downlink: conn.downlink || null },
    };
  }

  installNetworkTracking() {
    const emit = () => this.moduleEvent("NetInfo", "change", this.netInfoSnapshot());
    window.addEventListener("online", emit);
    window.addEventListener("offline", emit);
  }

  installVisibilityTracking() {
    document.addEventListener("visibilitychange", () => {
      const next = document.visibilityState === "hidden" ? "background" : "active";
      if (next === this.appState) return;
      this.appState = next;
      this.moduleEvent("AppState", "change", next);
    });
  }

  /** Present an iOS-style alert or action sheet; resolves with the chosen index (-1 on dismiss). */
  presentAlert({ title, message, buttons, style }) {
    return new Promise((resolve) => {
      const list = Array.isArray(buttons) && buttons.length ? buttons : [{ label: "OK", style: "default" }];
      const sheet = style === "action_sheet" || style === "sheet";
      const backdrop = document.createElement("div");
      backdrop.className = "pn-alert-backdrop" + (sheet ? " pn-sheet" : "");
      const box = document.createElement("div");
      box.className = "pn-alert" + (sheet ? " pn-sheet" : "");
      const body = document.createElement("div");
      body.className = "pn-alert-body";
      if (title) {
        const h = document.createElement("h2");
        h.textContent = String(title);
        body.appendChild(h);
      }
      if (message) {
        const p = document.createElement("p");
        p.textContent = String(message);
        body.appendChild(p);
      }
      box.appendChild(body);
      const row = document.createElement("div");
      row.className = "pn-alert-buttons" + (list.length > 2 || sheet ? " pn-vertical" : "");
      const finish = (index) => {
        backdrop.remove();
        resolve(index);
      };
      list.forEach((button, index) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = String(button.label ?? button.title ?? "OK");
        if (button.style === "cancel") b.classList.add("pn-cancel");
        if (button.style === "destructive") b.classList.add("pn-destructive");
        b.addEventListener("click", () => finish(index));
        row.appendChild(b);
      });
      box.appendChild(row);
      backdrop.appendChild(box);
      backdrop.addEventListener("click", (event) => {
        if (event.target !== backdrop) return;
        const cancel = list.findIndex((b) => b.style === "cancel");
        finish(cancel >= 0 ? cancel : sheet ? -1 : -1);
      });
      this.overlaysEl.appendChild(backdrop);
    });
  }
}

function nullish(value) {
  return value === undefined ? null : value;
}

/** `["Chrome", "144.0"]`-style browser name and version from a user agent string. */
export function browserFamily(userAgent) {
  const ua = userAgent || "";
  const probes = [
    ["Firefox", /Firefox\/([\d.]+)/],
    ["Edge", /Edg\/([\d.]+)/],
    ["Chrome", /Chrome\/([\d.]+)/],
    ["Safari", /Version\/([\d.]+).*Safari/],
  ];
  for (const [name, re] of probes) {
    const m = re.exec(ua);
    if (m) return [name, m[1].split(".").slice(0, 2).join(".")];
  }
  return ["Browser", "0"];
}
