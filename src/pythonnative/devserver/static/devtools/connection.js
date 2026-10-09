// The DevTools page's WebSocket to `pn start` (`/ws?role=devtools`).
//
// The socket authenticates with the dev token cookie the page received
// when it was opened from the URL `pn start` printed. It reconnects with
// backoff, and `rpc()` turns `rpc` / `rpc_result` pairs into promises.

export class Connection {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.state = "connecting"; // "connecting" | "open" | "closed"
    this.listeners = new Map(); // type -> Set<fn>
    this.pending = new Map(); // rpc id -> {resolve, reject, timer}
    this.nextId = 1;
    this.backoff = 500;
    this.timer = 0;
    this.everOpened = false;
  }

  /** Subscribe to a message type (`"targets"`, `"event"`, ...) or `"state"`. */
  on(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(fn);
    return () => this.listeners.get(type)?.delete(fn);
  }

  emit(type, payload) {
    for (const fn of this.listeners.get(type) || []) {
      try {
        fn(payload);
      } catch (err) {
        console.error(`[devtools] ${type} listener failed`, err);
      }
    }
  }

  connect() {
    clearTimeout(this.timer);
    this.setState("connecting");
    let socket;
    try {
      socket = new WebSocket(this.url);
    } catch (err) {
      this.retry();
      return;
    }
    this.socket = socket;
    socket.addEventListener("open", () => {
      this.backoff = 500;
      this.everOpened = true;
      this.setState("open");
    });
    socket.addEventListener("message", (event) => this.receive(event.data));
    socket.addEventListener("close", () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.failPending("the connection to pn start closed");
      this.setState("closed");
      this.retry();
    });
    socket.addEventListener("error", () => {
      /* close follows */
    });
  }

  retry() {
    clearTimeout(this.timer);
    const delay = this.backoff;
    this.backoff = Math.min(this.backoff * 1.6, 5000);
    this.timer = setTimeout(() => this.connect(), delay);
  }

  /** Reconnect now (the user asked), resetting the backoff. */
  reconnectNow() {
    this.backoff = 500;
    if (this.socket) return;
    this.connect();
  }

  setState(state) {
    if (state === this.state) return;
    this.state = state;
    this.emit("state", state);
  }

  receive(text) {
    let message;
    try {
      message = JSON.parse(text);
    } catch (err) {
      return;
    }
    if (!message || typeof message !== "object") return;
    if (message.type === "rpc_result") {
      const entry = this.pending.get(message.id);
      if (!entry) return;
      this.pending.delete(message.id);
      clearTimeout(entry.timer);
      if (message.error != null) entry.reject(new Error(String(message.error)));
      else entry.resolve(message.result);
      return;
    }
    this.emit(message.type, message);
  }

  send(message) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  /** Call devtools agent `method` on `target`; rejects on error, timeout, or disconnect. */
  rpc(target, method, params = {}, { timeout = 35000 } = {}) {
    if (!target) return Promise.reject(new Error("no app is selected"));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      if (!this.send({ type: "rpc", id, target, method, params })) {
        reject(new Error("not connected to pn start"));
        return;
      }
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out`));
      }, timeout);
      this.pending.set(id, { resolve, reject, timer });
    });
  }

  failPending(reason) {
    for (const entry of this.pending.values()) {
      clearTimeout(entry.timer);
      entry.reject(new Error(reason));
    }
    this.pending.clear();
  }
}
