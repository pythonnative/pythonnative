// Connect: the QR code a phone scans, the connect links, how to get
// PythonNative Go, and the debugger configuration.

import { Panel } from "./panel.js";
import { copyButton, h, kindBadge } from "../util.js";

/** The VS Code attach configuration `pn init` writes, for `port`. */
export function launchConfig(port) {
  return JSON.stringify(
    {
      name: "PythonNative: Attach",
      type: "debugpy",
      request: "attach",
      connect: { host: "127.0.0.1", port: Number(port) || 5678 },
      justMyCode: true,
    },
    null,
    2,
  );
}

export class ConnectPanel extends Panel {
  constructor(app) {
    super(app, "connect", "Connect");
    this.doc = null;
    this.el.classList.add("connect");
    this.render();
  }

  onConnectDoc(doc) {
    this.doc = doc;
    this.render();
  }

  onShow() {
    super.onShow();
    // Refresh: the LAN address or the debugger port may have changed.
    this.app.conn.send({ type: "connect" });
  }

  onTargets() {
    if (this.doc) this.renderDevices();
  }

  render() {
    const doc = this.doc;
    this.el.textContent = "";
    if (!doc) {
      this.el.appendChild(Panel.empty("Waiting for pn start..."));
      return;
    }
    const links = doc.links || {};
    const goCompatible = links.go_compatible !== false;
    const preferred = links.preferred || links.go || links.server;

    const qr = h("div.qr", { role: "img", "aria-label": "QR code for the connect link" });
    // The server renders the SVG (pythonnative.devserver.qr); it's same-origin markup.
    qr.innerHTML = doc.qr_svg || "";

    const scan = h(
      "section.card.connect-scan",
      null,
      qr,
      h(
        "div.scan-text",
        null,
        h("h2", null, "Open on a phone"),
        h(
          "p",
          null,
          goCompatible
            ? "Scan with the camera app to open this project in PythonNative Go. The phone needs to be on the same network as this computer."
            : "This project adds native code, so it runs in its own development build, not PythonNative Go. Build it once with pn run ios or pn run android, then scan to connect.",
        ),
        doc.lan ? null : h("p.notice", null, "No network address was found, so the code points at localhost. Connect this computer to Wi-Fi or Ethernet for phones to reach it."),
        this.linkRow("Connect link", preferred),
      ),
    );

    const linkRows = [];
    if (links.go) linkRows.push(this.linkRow("PythonNative Go", links.go));
    if (links.app) linkRows.push(this.linkRow("Development build", links.app));
    if (links.server) linkRows.push(this.linkRow("Server (LAN)", links.server));
    if (doc.local?.server) linkRows.push(this.linkRow("Server (this computer)", doc.local.server));
    if (doc.local?.go) linkRows.push(this.linkRow("Go on a simulator", doc.local.go));
    if (doc.devtools) linkRows.push(this.linkRow("DevTools", doc.devtools));

    const simulators = h(
      "section.card",
      null,
      h("h2", null, "Simulators and emulators"),
      h(
        "ol.steps",
        null,
        h("li", null, "In the terminal running ", h("code", null, "pn start"), ", press ", h("kbd", null, "i"), " for the iOS Simulator or ", h("kbd", null, "a"), " for the Android emulator."),
        h("li", null, "Or run ", h("code", null, "pn go ios"), " or ", h("code", null, "pn go android"), " in another terminal. It installs PythonNative Go (downloading it once per version), boots a device if none is running, and connects it."),
        h("li", null, "Press ", h("kbd", null, "I"), " or ", h("kbd", null, "A"), " to build and run the project's own debug build instead, which is what projects with native code use."),
      ),
    );

    const port = doc.debug_port;
    const debug = h(
      "section.card",
      null,
      h("h2", null, "Debugger"),
      port === 0
        ? h("p", null, "The debugger proxy is off (pn start --debug-port 0).")
        : [
            h(
              "p",
              null,
              "Breakpoints use debugpy. In VS Code, run the ",
              h("strong", null, "PythonNative: Attach"),
              ` configuration; it connects to 127.0.0.1:${port || 5678}, and pn start forwards the session to the selected app. `,
              "Choose which app with \"Debug this app\" in the header.",
            ),
            h("div.code-head", null, h("span", null, ".vscode/launch.json configuration"), copyButton(() => launchConfig(port))),
            h("pre.code", null, launchConfig(port)),
          ],
    );

    this.devices = h("section.card");
    this.el.append(
      h("div.connect-grid", null, scan, h("section.card", null, h("h2", null, "Links"), linkRows), this.devices, simulators, debug),
    );
    this.renderDevices();
  }

  renderDevices() {
    const box = this.devices;
    if (!box) return;
    box.textContent = "";
    box.appendChild(h("h2", null, "Connected apps"));
    const targets = this.app.targets;
    if (!targets.length) {
      box.appendChild(h("p.muted", null, "Nothing is connected yet."));
      return;
    }
    const list = h("ul.device-list");
    for (const target of targets) {
      const since = target.connected_at ? new Date(target.connected_at * 1000).toLocaleTimeString() : "";
      const badge = kindBadge(target.kind);
      list.appendChild(
        h(
          "li",
          null,
          h(`span.badge.${badge.cls}`, null, badge.text),
          h("span.device-label", null, target.label || target.id),
          since ? h("span.muted", null, `since ${since}`) : null,
        ),
      );
    }
    box.appendChild(list);
  }

  linkRow(label, url) {
    if (!url) return null;
    return h(
      "div.link-row",
      null,
      h("span.link-label", null, label),
      h("code.link-url", { title: url }, url),
      copyButton(url),
    );
  }
}
