// The page's half of the PythonNative bridge.
//
// Python (`pythonnative.bridge.web.WebTransport`) sends JSON arrays over
// one WebSocket. Fire-and-forget messages carry no id; requests carry an
// id in slot 1 and are answered with ["res", id, result]. The same shape
// works in the other direction: the page raises `callback(kind, tag,
// name, payload)` as ["cb", ...] (no reply) or ["req", id, ...] (Python
// answers with ["res", id, text]).
//
// Payloads that the native protocol carries as JSON *text* stay text
// here too (`args`, `request`, `payload`, `result`), so the page and
// Python reuse their existing codecs unchanged.

export class Bridge {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.nextId = 1;
    this.pending = new Map(); // id -> {resolve}
    this.handlers = {}; // kind -> async (message) => result
    this.onOpen = null;
    this.onClose = null;
    this.onDev = null;
    this.connected = false;
    this._backoff = 500;
    this._closedByUs = false;
  }

  connect() {
    this._closedByUs = false;
    let socket;
    try {
      socket = new WebSocket(this.url);
    } catch (err) {
      this._scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.addEventListener("open", () => {
      this.connected = true;
      this._backoff = 500;
      if (this.onOpen) this.onOpen();
    });
    socket.addEventListener("message", (event) => this._onMessage(event.data));
    socket.addEventListener("close", (event) => {
      const wasConnected = this.connected;
      this.connected = false;
      this.socket = null;
      for (const waiter of this.pending.values()) waiter.resolve(null);
      this.pending.clear();
      if (this.onClose) this.onClose(wasConnected, event);
      if (!this._closedByUs) this._scheduleReconnect();
    });
    socket.addEventListener("error", () => {
      /* close follows */
    });
  }

  close() {
    this._closedByUs = true;
    if (this.socket) this.socket.close();
  }

  _scheduleReconnect() {
    const delay = this._backoff;
    this._backoff = Math.min(this._backoff * 1.5, 4000);
    setTimeout(() => this.connect(), delay);
  }

  send(message) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  // -- page -> Python -------------------------------------------------

  /** Fire-and-forget callback: `callback(kind, tag, name, payload)`. */
  callback(kind, tag, name, payload) {
    return this.send(["cb", kind, tag, name, payload == null ? "" : payload]);
  }

  /** Callback that needs Python's answer (row binds, screen creation). */
  request(kind, tag, name, payload) {
    const id = this.nextId++;
    return new Promise((resolve) => {
      if (!this.send(["req", id, kind, tag, name, payload == null ? "" : payload])) {
        resolve(null);
        return;
      }
      this.pending.set(id, { resolve });
    });
  }

  /** Dev-channel message (logs, errors) shown in the `pn start` terminal. */
  dev(payload) {
    return this.send(["dev", payload]);
  }

  // -- Python -> page -------------------------------------------------

  async _onMessage(text) {
    let message;
    try {
      message = JSON.parse(text);
    } catch (err) {
      console.error("[pn] malformed message", text.slice(0, 200));
      return;
    }
    if (!Array.isArray(message) || message.length === 0) return;
    const kind = message[0];
    if (kind === "res") {
      const waiter = this.pending.get(message[1]);
      if (waiter) {
        this.pending.delete(message[1]);
        waiter.resolve(message.length > 2 ? message[2] : null);
      }
      return;
    }
    if (kind === "dev") {
      if (this.onDev) this.onDev(message[1] || {});
      return;
    }
    const handler = this.handlers[kind];
    if (!handler) {
      console.warn("[pn] unhandled message kind", kind);
      if (kind !== "apply" && message.length > 1 && typeof message[1] === "number") {
        this.send(["res", message[1], null]);
      }
      return;
    }
    if (kind === "apply") {
      try {
        handler(message);
      } catch (err) {
        this.reportError("apply failed", err);
      }
      return;
    }
    const id = message[1];
    let result = null;
    try {
      result = await handler(message);
    } catch (err) {
      this.reportError(`${kind} failed`, err);
    }
    if (id != null) this.send(["res", id, result === undefined ? null : result]);
  }

  reportError(context, err) {
    const detail = err && err.stack ? err.stack : String(err);
    console.error(`[pn] ${context}:`, err);
    this.dev({ type: "error", text: `${context}: ${detail}` });
  }
}
