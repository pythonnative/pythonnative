// The browser preview's half of the renderer core (RFC 0007).
//
// `pn_core.js` and `pn_core.wasm` are the C++ core the iOS and Android apps
// link, compiled to WebAssembly by `scripts/build-core-wasm.py`. This module
// binds its C ABI (`native/core/include/pn_core.h`), decodes the binary mount
// transactions and animated writes it produces, and makes the page the
// core's platform: `CoreHost` installs the `pn_platform` callbacks, drains
// mount transactions into the DOM renderer, runs deferred work and the
// animation frame clock, and polls gesture deadlines.
//
// The page is single-threaded. The core calls `measure`, `baseline`, and
// `emit` synchronously from inside a commit or a layout; those callbacks
// never call back into the core. Mounting, deferred work, and frames run on
// later turns of the event loop (a microtask, a timer, and
// `requestAnimationFrame`), as the UI thread does on device.
//
// The ABI uses wasm32 pointers (numbers) and int64 values as BigInts.

import createCore from "./pn_core.js";

export const PROTOCOL_VERSION = 7;
export const MEASURE_TEXT = 1;
export const MEASURE_INTRINSIC = 2;
export const MEASURE_NATIVE = 3;
export const POINTER_DOWN = 0;
export const POINTER_MOVE = 1;
export const POINTER_UP = 2;
export const POINTER_CANCEL = 3;

const MAGIC = 0x544d4e50; // "PNMT"
const POINTER_EVENT_SIZE = 48; // pn_pointer_event on wasm32
const utf8 = new TextDecoder();

// ---------------------------------------------------------------------------
// Decoding (mirrors `decode_transaction` in `pythonnative/bridge/core.py`)
// ---------------------------------------------------------------------------

class Reader {
  constructor(bytes) {
    this.bytes = bytes;
    this.data = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    this.offset = 0;
  }
  u8() { return this.data.getUint8(this.offset++); }
  u16() { const v = this.data.getUint16(this.offset, true); this.offset += 2; return v; }
  u32() { const v = this.data.getUint32(this.offset, true); this.offset += 4; return v; }
  i64() { const v = this.data.getBigInt64(this.offset, true); this.offset += 8; return Number(v); }
  f64() { const v = this.data.getFloat64(this.offset, true); this.offset += 8; return v; }
  str() {
    const length = this.u32();
    const text = utf8.decode(this.bytes.subarray(this.offset, this.offset + length));
    this.offset += length;
    return text;
  }
  value() {
    const kind = this.u8();
    switch (kind) {
      case 0: return null;
      case 1: return false;
      case 2: return true;
      case 3: return this.i64();
      case 4: return this.f64();
      case 5: return this.str();
      case 6: { const out = []; for (let n = this.u32(); n > 0; n--) out.push(this.value()); return out; }
      case 7: {
        const out = {};
        for (let n = this.u32(); n > 0; n--) { const key = this.str(); out[key] = this.value(); }
        return out;
      }
      default: throw new Error(`Unknown value kind ${kind} in a mount transaction`);
    }
  }
}

/** One encoded value (measurement requests carry props this way). */
export function decodeValue(bytes) {
  return new Reader(bytes).value();
}

/**
 * Decode a mount transaction into `{surface, revision, id, ops}`. Each op is
 * `{kind, tag, ...}` with the fields Python's `MountOp` uses: `component` and
 * `props` (create); `props`, `removed`, and `recreate` (update); `parent` and
 * `index` (insert); `frame` (frame); `name`, `arguments`, and `call_id` (command).
 */
export function decodeTransaction(bytes) {
  const r = new Reader(bytes);
  if (r.u32() !== MAGIC) throw new Error("Not a mount transaction");
  r.u16(); r.u16();
  const surface = r.i64(), revision = r.i64(), id = r.i64();
  const ops = [];
  for (let n = r.u32(); n > 0; n--) {
    const code = r.u8();
    switch (code) {
      case 0: ops.push({kind: "reset"}); break;
      case 1: { const tag = r.i64(); const component = r.str(); ops.push({kind: "create", tag, component, props: r.value()}); break; }
      case 2: {
        const tag = r.i64(), flags = r.u8(), props = r.value(), removed = [];
        for (let count = r.u32(); count > 0; count--) removed.push(r.str());
        ops.push({kind: "update", tag, props, removed, recreate: !!(flags & 1)});
        break;
      }
      case 3: { const parent = r.i64(), tag = r.i64(); ops.push({kind: "insert", tag, parent, index: r.u32()}); break; }
      case 5: ops.push({kind: "delete", tag: r.i64()}); break;
      case 6: { const tag = r.i64(); ops.push({kind: "frame", tag, frame: [r.f64(), r.f64(), r.f64(), r.f64()]}); break; }
      case 7: {
        const tag = r.i64(), name = r.str(), args = r.value();
        ops.push({kind: "command", tag, name, arguments: args, call_id: r.i64()});
        break;
      }
      default: throw new Error(`Unknown mount op ${code}`);
    }
  }
  return {surface, revision, id, ops};
}

/** Decode animated prop writes into `[tag, prop, value]` triples. */
export function decodeWrites(bytes) {
  const r = new Reader(bytes), out = [];
  for (let n = r.u32(); n > 0; n--) out.push([r.i64(), r.str(), r.value()]);
  return out;
}

// ---------------------------------------------------------------------------
// The C ABI
// ---------------------------------------------------------------------------

const big = (value) => BigInt(Math.trunc(Number(value) || 0));

/** The bound C ABI of one WebAssembly core instance (`pn_core_shared`). */
export class RendererCore {
  /** Instantiate `pn_core.wasm` (next to this module unless `options.locateFile` says otherwise). */
  static async load(options = {}) {
    return new RendererCore(await createCore(options));
  }

  constructor(module) {
    this.module = module;
    this.handle = module._pn_core_shared();
    // pn_bytes (data, size) and a uint64 id for the out-parameters.
    this.scratch = module._malloc(16);
    this.callbacks = [];
  }

  view() { return new DataView(this.module.HEAPU8.buffer); }

  /** Copy `size` bytes out of WASM memory (later calls may grow and move it). */
  copy(pointer, size) { return this.module.HEAPU8.slice(pointer, pointer + size); }

  /** A string the core returned, copied and released with `pn_core_free`. */
  take(pointer) {
    if (!pointer) return null;
    try { return this.module.UTF8ToString(pointer); } finally { this.module._pn_core_free(pointer); }
  }

  /** Call `fn` with each of `values` as a NUL-terminated UTF-8 copy in WASM memory. */
  strings(values, fn) {
    const m = this.module, pointers = [];
    try {
      for (const value of values) {
        if (value == null) { pointers.push(0); continue; }
        const text = String(value), size = m.lengthBytesUTF8(text) + 1, pointer = m._malloc(size);
        m.stringToUTF8(text, pointer, size);
        pointers.push(pointer);
      }
      return fn(...pointers);
    } finally {
      for (const pointer of pointers) if (pointer) m._free(pointer);
    }
  }

  // -- setup ------------------------------------------------------------

  protocolVersion() { return this.module._pn_core_protocol_version(); }

  /**
   * Install the platform callbacks: `scheduleMount()`, `scheduleWork()`,
   * `requestFrames()`, `measure(request) -> [width, height]`,
   * `baseline(surface, tag, width, height) -> number`, and
   * `emit(kind, surface, tag, name, payload)`. A callback must never throw
   * into the core, so each one is guarded here.
   */
  setPlatform(platform) {
    const m = this.module;
    const guard = (label, fn, fallback) => (...args) => {
      try { return fn(...args); } catch (error) { console.error(`[pn core] ${label} failed`, error); return fallback; }
    };
    const functions = [
      m.addFunction(guard("schedule_mount", () => platform.scheduleMount()), "vi"),
      m.addFunction(guard("schedule_work", () => platform.scheduleWork()), "vi"),
      m.addFunction(guard("request_frames", () => platform.requestFrames()), "vi"),
      m.addFunction(guard("measure", (context, request, size) => this.measureCallback(platform, request, size)), "viii"),
      m.addFunction(guard("baseline", (context, surface, tag, width, height) => {
        const value = Number(platform.baseline(Number(surface), Number(tag), width, height));
        return Number.isFinite(value) ? value : height;
      }, 0), "fijjff"),
      m.addFunction(guard("emit", (context, kind, surface, tag, name, payload) => platform.emit(
        m.UTF8ToString(kind), Number(surface), Number(tag), name ? m.UTF8ToString(name) : "", payload ? m.UTF8ToString(payload) : "",
      )), "viijjii"),
    ];
    this.callbacks = functions;
    // pn_platform: void *context, then six function pointers (table indices).
    const struct = m._malloc(4 * 7), view = this.view();
    view.setUint32(struct, 0, true);
    functions.forEach((index, i) => view.setUint32(struct + 4 * (i + 1), index, true));
    m._pn_core_set_platform(this.handle, struct);
    m._free(struct); // the core copies the struct
  }

  measureCallback(platform, request, size) {
    // pn_measure_request on wasm32: i64 surface, i64 tag, char *component,
    // i32 mode, pn_bytes props, f32 width, i32 width_mode, f32 height,
    // i32 height_mode.
    const view = this.view();
    const props = view.getUint32(request + 24, true), propsSize = view.getUint32(request + 28, true);
    const measured = platform.measure({
      surface: Number(view.getBigInt64(request, true)),
      tag: Number(view.getBigInt64(request + 8, true)),
      component: this.module.UTF8ToString(view.getUint32(request + 16, true)),
      mode: view.getInt32(request + 20, true),
      props: propsSize ? decodeValue(this.copy(props, propsSize)) : {},
      width: view.getFloat32(request + 32, true),
      widthMode: view.getInt32(request + 36, true),
      height: view.getFloat32(request + 40, true),
      heightMode: view.getInt32(request + 44, true),
    }) || [0, 0];
    const out = this.view();
    out.setFloat32(size, finite(measured[0]), true);
    out.setFloat32(size + 4, finite(measured[1]), true);
  }

  /** Compile a contract document; returns `null` or the core's error message. */
  loadContracts(document, platform = "web") {
    return this.strings([document, platform], (doc, name) => this.take(this.module._pn_core_load_contracts(this.handle, doc, name)));
  }

  fingerprint() { return this.take(this.module._pn_core_contract_fingerprint(this.handle)) || ""; }
  setFlattening(enabled) { this.module._pn_core_set_flattening(this.handle, enabled ? 1 : 0); }
  /** Forget every surface, queued transaction, and contract. */
  reset() { this.module._pn_core_reset(this.handle); }

  // -- Python's side ------------------------------------------------------

  commit(envelope) { return this.strings([envelope], (text) => this.take(this.module._pn_core_commit(this.handle, text))) || ""; }
  layout(request) { return this.strings([request], (text) => this.take(this.module._pn_core_layout(this.handle, text))) || ""; }
  command(surface, tag, name, args, callId) {
    return this.strings([name, args || "{}"], (n, a) => this.take(this.module._pn_core_command(this.handle, big(surface), big(tag), n, a, big(callId)))) || "";
  }
  animate(surface, tag, request) {
    return this.strings([request], (text) => this.take(this.module._pn_core_animate(this.handle, big(surface), big(tag), text))) || "";
  }
  measure(surface, tag) { return this.take(this.module._pn_core_measure(this.handle, big(surface), big(tag))) || "null"; }
  inspect(surface, x, y) { return this.take(this.module._pn_core_inspect(this.handle, big(surface), x, y)) || "null"; }
  validateModule(module, method, args) {
    return this.strings([module, method, args], (a, b, c) => this.module._pn_core_validate_module(this.handle, a, b, c) !== 0);
  }
  /** Whether a JSON value satisfies a JSON-schema contract, as the core checks props. */
  checkValue(schema, value) {
    return this.strings([JSON.stringify(schema), JSON.stringify(value)], (s, v) => this.module._pn_core_check_value(s, v) !== 0);
  }
  work() { this.module._pn_core_work(this.handle); }

  // -- the UI thread's side --------------------------------------------------

  /** The next queued transaction as `{bytes, id}` (bytes copied), or `null`. */
  mountNext() {
    const s = this.scratch;
    if (!this.module._pn_core_mount_next(this.handle, s, s + 8)) return null;
    const view = this.view();
    return {bytes: this.copy(view.getUint32(s, true), view.getUint32(s + 4, true)), id: view.getBigUint64(s + 8, true)};
  }
  mountFinished(id, error = null) {
    this.strings([error], (e) => this.module._pn_core_mount_finished(this.handle, BigInt(id), e));
  }
  isMounted(surface, tag) { return this.module._pn_core_is_mounted(this.handle, big(surface), big(tag)) !== 0; }
  reportContainer(surface, tag, x, y, width, height) {
    this.module._pn_core_report_container(this.handle, big(surface), big(tag), x, y, width, height);
  }
  reportIntrinsic(surface, tag, width, height) { this.module._pn_core_report_intrinsic(this.handle, big(surface), big(tag), width, height); }
  invalidate(surface, tag) { this.module._pn_core_invalidate(this.handle, big(surface), big(tag)); }
  invalidateMeasurements() { this.module._pn_core_invalidate_measurements(this.handle); }
  /** Stamp a view event; the core emits the envelope for Python. `args` is JSON text. */
  event(surface, tag, name, args, editRevision = 0) {
    this.strings([name, args], (n, a) => this.module._pn_core_event(this.handle, big(surface), big(tag), n, a, big(editRevision)));
  }
  animationFrame(timestampMs) { return this.module._pn_core_animation_frame(this.handle, timestampMs) !== 0; }
  takeWrites() {
    const s = this.scratch;
    if (!this.module._pn_core_take_writes(this.handle, s)) return [];
    const view = this.view(), size = view.getUint32(s + 4, true);
    return size ? decodeWrites(this.copy(view.getUint32(s, true), size)) : [];
  }
  setReduceMotion(enabled) { this.module._pn_core_set_reduce_motion(this.handle, enabled ? 1 : 0); }

  /**
   * Feed `{phase, pointer, x, y, windowX, windowY, time}` events (points and
   * seconds) to a view's gestures; returns whether a pan is active.
   */
  pointer(surface, tag, events) {
    if (!events.length) return false;
    const m = this.module, pointer = m._malloc(POINTER_EVENT_SIZE * events.length);
    try {
      const view = this.view();
      events.forEach((event, i) => {
        const at = pointer + i * POINTER_EVENT_SIZE;
        view.setInt32(at, event.phase, true);
        view.setInt32(at + 4, event.pointer | 0, true);
        view.setFloat64(at + 8, event.x, true);
        view.setFloat64(at + 16, event.y, true);
        view.setFloat64(at + 24, event.windowX ?? event.x, true);
        view.setFloat64(at + 32, event.windowY ?? event.y, true);
        view.setFloat64(at + 40, event.time, true);
      });
      return m._pn_core_pointer(this.handle, big(surface), big(tag), pointer, events.length) !== 0;
    } finally {
      m._free(pointer);
    }
  }
  /** When a view's gestures next need polling (seconds), or `null`. */
  gestureDeadline(surface, tag) {
    const value = this.module._pn_core_gesture_deadline(this.handle, big(surface), big(tag));
    return value < 0 ? null : value;
  }
  gesturePoll(surface, tag, time) { this.module._pn_core_gesture_poll(this.handle, big(surface), big(tag), time); }
  hasGestures(surface, tag) { return this.module._pn_core_has_gestures(this.handle, big(surface), big(tag)) !== 0; }

  // -- list data sources ----------------------------------------------------

  /** Publish a list's next queued dataset patch; returns its edits, or `null`. */
  listApply(surface, tag) {
    const text = this.take(this.module._pn_core_list_apply(this.handle, big(surface), big(tag)));
    return text == null ? null : JSON.parse(text);
  }
  listRevision(surface, tag) { return Number(this.module._pn_core_list_revision(this.handle, big(surface), big(tag))); }
  listCount(surface, tag) { return Number(this.module._pn_core_list_count(this.handle, big(surface), big(tag))); }
  listKey(surface, tag, index) { return this.take(this.module._pn_core_list_key(this.handle, big(surface), big(tag), big(index))); }
  listIndex(surface, tag, key) {
    return Number(this.strings([key], (k) => this.module._pn_core_list_index(this.handle, big(surface), big(tag), k)));
  }
  listExtent(surface, tag, index) { return this.module._pn_core_list_extent(this.handle, big(surface), big(tag), big(index)); }
  listSticky(surface, tag, index) { return this.module._pn_core_list_sticky(this.handle, big(surface), big(tag), big(index)) !== 0; }
  listRowRevision(surface, tag, index) { return Number(this.module._pn_core_list_row_revision(this.handle, big(surface), big(tag), big(index))); }
  listStickyAt(surface, tag, index) { return Number(this.module._pn_core_list_sticky_at(this.handle, big(surface), big(tag), big(index))); }
}

function finite(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

// ---------------------------------------------------------------------------
// The page as the core's platform
// ---------------------------------------------------------------------------

/**
 * Connects one core to the DOM renderer: the UI thread of the preview.
 *
 * `send(kind, tag, name, payload)` delivers the core's messages (events,
 * layout, animation, host) and command results to Python.
 */
export class CoreHost {
  constructor(core, renderer, {send}) {
    this.core = core;
    this.renderer = renderer;
    this.send = send;
    this.mountQueued = false;
    this.draining = false;
    this.workTimer = 0;
    this.frameHandle = 0;
    this.gestureTimers = new Map();
    renderer.attach(this);
    core.setPlatform({
      scheduleMount: () => this.scheduleMount(),
      scheduleWork: () => this.scheduleWork(),
      requestFrames: () => this.requestFrames(),
      measure: (request) => renderer.measure(request),
      baseline: (surface, tag, width, height) => renderer.baseline(tag, width, height),
      emit: (kind, surface, tag, name, payload) => this.send(kind, tag, name, payload),
    });
    this.watchReduceMotion();
  }

  // -- platform callbacks ---------------------------------------------------

  scheduleMount() {
    if (this.mountQueued) return;
    this.mountQueued = true;
    queueMicrotask(() => this.drain());
  }

  scheduleWork() {
    if (this.workTimer) return;
    this.workTimer = setTimeout(() => {
      this.workTimer = 0;
      this.core.work();
      this.drain();
    }, 0);
  }

  requestFrames() {
    if (this.frameHandle) return;
    this.frameHandle = requestAnimationFrame((time) => this.frame(time));
  }

  frame(time) {
    this.frameHandle = 0;
    const running = this.core.animationFrame(time);
    this.applyWrites();
    if (running) this.requestFrames();
  }

  // -- mounting ---------------------------------------------------------------

  /** Apply every queued transaction now (module calls and tests call this first). */
  drain() {
    this.mountQueued = false;
    if (this.draining) return;
    this.draining = true;
    try {
      for (let next = this.core.mountNext(); next; next = this.core.mountNext()) {
        let error = null;
        try {
          this.renderer.applyTransaction(decodeTransaction(next.bytes));
        } catch (failure) {
          console.error("[pn] mount transaction failed", failure);
          error = String(failure?.message || failure);
        }
        this.core.mountFinished(next.id, error);
        this.applyWrites();
      }
    } finally {
      this.draining = false;
    }
  }

  /** Run deferred work (relayout after a container or image reported) right away. */
  flush() {
    if (this.workTimer) {
      clearTimeout(this.workTimer);
      this.workTimer = 0;
      this.core.work();
    }
    this.drain();
  }

  applyWrites() {
    for (const [tag, prop, value] of this.core.takeWrites()) this.renderer.applyAnimated(tag, prop, value);
  }

  /** A view's command ran (or failed); Python resolves the awaiting future. */
  commandResult(callId, ok, value, error) {
    const reply = ok ? {call_id: callId, ok: true, value: value === undefined ? null : value} : {call_id: callId, ok: false, error};
    this.send("command", 0, "", JSON.stringify(reply));
  }

  // -- input --------------------------------------------------------------------

  event(surface, tag, name, args, editRevision = 0) {
    this.core.event(surface, tag, name, JSON.stringify(args ?? []), editRevision);
    this.applyWrites();
  }

  /** Feed pointer events to a view's gestures and poll its time-based recognizers. */
  pointer(surface, tag, events) {
    const active = this.core.pointer(surface, tag, events);
    this.applyWrites();
    this.scheduleGesturePoll(surface, tag);
    return active;
  }

  scheduleGesturePoll(surface, tag) {
    const deadline = this.core.gestureDeadline(surface, tag);
    const pending = this.gestureTimers.get(tag);
    if (pending && (deadline == null || pending.deadline <= deadline + 0.001)) return;
    if (pending) clearTimeout(pending.timer);
    this.gestureTimers.delete(tag);
    if (deadline == null) return;
    const delay = Math.max(1, (deadline - performance.now() / 1000) * 1000);
    const timer = setTimeout(() => {
      this.gestureTimers.delete(tag);
      if (!this.renderer.views.has(tag)) return;
      this.core.gesturePoll(surface, tag, performance.now() / 1000);
      this.applyWrites();
      this.scheduleGesturePoll(surface, tag);
    }, delay);
    this.gestureTimers.set(tag, {deadline, timer});
  }

  forgetGestures(tag) {
    const pending = this.gestureTimers.get(tag);
    if (pending) clearTimeout(pending.timer);
    this.gestureTimers.delete(tag);
  }

  watchReduceMotion() {
    let query = null;
    try { query = matchMedia("(prefers-reduced-motion: reduce)"); } catch (error) { return; }
    const apply = () => this.core.setReduceMotion(!!query.matches);
    apply();
    query.addEventListener?.("change", apply);
  }

  // -- requests from Python ------------------------------------------------------

  loadContracts(document) { return this.core.loadContracts(document, "web"); }
  commit(envelope) { return this.core.commit(envelope); }
  layout(request) { return this.core.layout(request); }
  command(surface, tag, name, args, callId) { return this.core.command(surface, tag, name, args, callId); }
  animate(surface, tag, request) { return this.core.animate(surface, tag, request); }
  measure(surface, tag) { return this.core.measure(surface, tag); }

  /** The page went away from Python: forget the core's state and every view. */
  reset() {
    clearTimeout(this.workTimer);
    this.workTimer = 0;
    if (this.frameHandle) cancelAnimationFrame(this.frameHandle);
    this.frameHandle = 0;
    for (const {timer} of this.gestureTimers.values()) clearTimeout(timer);
    this.gestureTimers.clear();
    this.core.reset();
    this.renderer.reset();
  }
}

/** Load the WebAssembly core and connect it to `renderer`. */
export async function startCore(renderer, {send, locateFile} = {}) {
  const core = await RendererCore.load(locateFile ? {locateFile} : {});
  if (core.protocolVersion() !== PROTOCOL_VERSION) {
    throw new Error(`The WebAssembly core speaks protocol ${core.protocolVersion()}, but the page expects ${PROTOCOL_VERSION}`);
  }
  return new CoreHost(core, renderer, {send});
}
