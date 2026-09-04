# The native bridge

PythonNative renders through a **native rendering core**: Python owns
the component tree, reconciliation, and layout, while Swift
(`PythonNativeKit`) and Kotlin (the `pythonnative` Gradle module) own
every native view, gesture recognizer, animation, and device API. The
two sides talk through a small, versioned protocol described on this
page. If you're porting a component manager or a native module, this is
the contract to implement.

The design mirrors React Native's Fabric and TurboModules: one
serialized transaction per commit, synchronous measurement, a
tag-addressed event channel back into Python, and a module registry
that lets a PyPI package ship Swift and Kotlin alongside its Python.

## Why a bridge

Before the bridge, PythonNative drove `UIView` and `android.view.View`
objects directly from Python through `rubicon-objc` and Chaquopy. Every
prop write, every `frame` assignment, and every measurement was its own
foreign-function call, and iOS relied on raw `libobjc` calls that were
prone to crashing on arm64. The bridge replaces that with:

- **One crossing per commit.** The reconciler serializes its mutation
  batch to JSON and hands the whole transaction to native in a single
  call. Native applies it on the UI thread.
- **Native component managers.** Each element type (`Text`, `Image`,
  `ScrollView`, ...) has a Swift `PNComponentManager` and a Kotlin
  `ComponentManager` that create views, apply props, position children,
  and report intrinsic sizes.
- **Native modules.** Device APIs (`Camera`, `Location`, `Storage`,
  ...) are Swift and Kotlin classes registered by name. Python facades
  call them through one `call(module, method, args)` entry point and
  receive results synchronously or through promises.
- **No Python-side ObjC or JNI.** `rubicon-objc` is gone as a
  dependency; Chaquopy is used only to reach the single `PNBridge`
  class.

## Transport

The wire format is JSON on both platforms. Payloads are small (a
commit is typically a few kilobytes) and JSON decoders on both
platforms are fast and well-tested, which matters more than raw
throughput at this size.

### iOS

`PythonNativeKit` exports C symbols with `@_cdecl`. Python loads them
through `ctypes.PyDLL(None)` (the running process), which keeps the GIL
held across the call so the main thread is never parked mid-commit.

```c
void  pn_bridge_apply(const char *transaction_json);
void  pn_bridge_measure(int64_t tag, double max_w, double max_h,
                        double *out_w, double *out_h);
char *pn_bridge_command(int64_t tag, const char *name, const char *args_json);
char *pn_bridge_animate(int64_t tag, const char *request_json);
char *pn_bridge_call(const char *module, const char *method, const char *args_json);
void  pn_bridge_free(char *ptr);
void  pn_bridge_set_callback(pn_callback_fn fn);
int   pn_bridge_protocol_version(void);
```

Strings returned by native are `strdup`'d; Python copies them and calls
`pn_bridge_free`. `pn_callback_fn` is the Python entry point native
uses for the reverse direction:

```c
typedef const char *(*pn_callback_fn)(const char *kind, int64_t tag,
                                      const char *name, const char *payload_json);
```

The returned string (when non-null) is owned by Python and valid until
the next callback returns; native copies it immediately.

### Android

The Kotlin module exposes `com.pythonnative.runtime.PNBridge`, a class
with static methods mirroring the C entry points. Python reaches it
through Chaquopy's `jclass`; this is the only Java class Python touches.

```kotlin
object PNBridge {
    @JvmStatic fun apply(transactionJson: String)
    @JvmStatic fun measure(tag: Long, maxWidth: Double, maxHeight: Double): String // "w,h"
    @JvmStatic fun command(tag: Long, name: String, argsJson: String): String?
    @JvmStatic fun animate(tag: Long, requestJson: String): String?
    @JvmStatic fun call(module: String, method: String, argsJson: String): String?
    @JvmStatic fun protocolVersion(): Int
    @JvmStatic fun setHost(host: PythonHost)
}

interface PythonHost {
    fun callback(kind: String, tag: Long, name: String, payloadJson: String): String?
}
```

The app template installs a `PythonHost` that forwards to
`pythonnative.bridge.native_callback` through Chaquopy. The library
module itself has no Chaquopy dependency, so it can be unit-tested with
plain JUnit.

### Threading

Every call in both directions happens on the platform main thread.
Python's asyncio loop already lives there (see the runtime docs), so
commits, measurements, commands, and callbacks never marshal across
threads. Native modules that complete on a background queue must hop
to the main thread before resolving a promise; the module base classes
do this for you.

### Versioning

`pn_bridge_protocol_version()` / `PNBridge.protocolVersion()` return
the protocol version compiled into the native library. Python refuses
to start when it doesn't match `pythonnative.bridge.PROTOCOL_VERSION`,
with a message pointing at `pn build` to re-stage the template.

## Transactions

A transaction is a JSON array of ops, applied strictly in order. Each
op is an array whose first element is a one-letter opcode:

| Opcode | Shape | Meaning |
| --- | --- | --- |
| `c` | `["c", tag, "Type", {props}]` | Create a view of `Type` with initial props |
| `u` | `["u", tag, {changed}]` | Apply changed props (`null` means removed) |
| `i` | `["i", parent, child, index]` | Ensure `child` is at `index` under `parent` (move-aware) |
| `d` | `["d", tag]` | Destroy the view and release its resources |
| `f` | `["f", tag, x, y, w, h]` | Set the frame, in points, relative to the parent's content origin |

Props are plain JSON. The Python side normalizes values before
encoding: `frozenset` and `tuple` become arrays, `math.inf` is emitted
as the string `"inf"`, and values that can't be encoded (Python
callables such as `render_row`) are held in a Python-side sidecar and
never sent. The prop `_pn_events` is an array of event names wired on
the element; managers use it to attach listeners lazily (a scroll
delegate only when `on_scroll` is present, for example).

Failures are isolated per op. Native logs the failing op and continues
with the rest of the transaction so a bad prop can't desync the tree.
Unknown element types create a placeholder view and log once.

The first native root's frame is owned by the screen host (it is placed
below the safe area on iOS and matched to the fragment container on
Android); the layout pass never emits an `f` op for it.

## Measurement

The Python layout engine calls `measure(tag, max_w, max_h)` for
content-sized leaves. Native returns the view's natural size given the
constraints; either constraint may be `1e6` meaning unconstrained. The
call is synchronous and happens after the create/update ops of the
current commit have been applied, so the view already carries its
current props.

## Commands

`command(tag, name, args_json)` runs an imperative action on one view
(`scroll_to_offset`, `focus`, `blur`, `get_scroll_offset`, ...) and
returns an optional JSON result. Managers ignore unknown commands.

## Events

Native emits events through the callback with `kind = "event"`:

```text
callback("event", tag, "on_press", "[]")
callback("event", tag, "on_change", "[\"new text\"]")
callback("event", tag, "gesture:0", "[{\"kind\":\"pan\",\"state\":\"changed\",...}]")
```

The payload is a JSON array of positional arguments, matching each
prop's documented signature. Python routes the event through
`pythonnative.events.dispatch_event`. A handler may return a value for
synchronous request-style events; the bridge encodes it as JSON and
returns it to native. The list row protocol below relies on this.

### Gesture payloads

Gesture recognizers post to `gesture:<index>` with a single dict
argument carrying `kind`, `state`, `x`, `y`, `translation_x`,
`translation_y`, `velocity_x`, `velocity_y`, `scale`, `rotation`,
`pointer_count`, and `direction`. The `gestures` prop is the list of
specs produced by `pythonnative.gestures.serialize_gestures`; each spec
has `kind`, per-kind configuration, `simultaneous` (indices allowed to
recognize together), and `wait_for` (indices that must fail first).
Recognition itself is native on every platform.

## Virtualized lists

`VirtualList` is backed by `UITableView` and `RecyclerView`. Rows host
full PythonNative subtrees driven by nested reconcilers, so the
platform asks Python for rows on demand:

1. Native needs a row for a recycled container. It emits
   `on_bind_row` with `[{"container": key, "index": i, "width": w, "height": h}]`
   and blocks on the result.
2. Python mounts or rebinds a `RowSubtree` for `(list tag, key)`. The
   subtree's create ops flow through `apply` re-entrantly inside the
   callback.
3. Python returns `{"root": root_tag}`. Native attaches the view with
   that tag into the container.
4. When a container is recycled or the list is destroyed, native emits
   `on_unbind_row` with `[{"container": key}]` (or the list's `d` op
   arrives) and Python unmounts the subtree.

Scroll reports arrive as `on_scroll` with `{"x", "y", "extent", "range"}`.

## Animations

`animate(tag, request_json)` drives a view's animatable properties
(`opacity`, `background_color`, `translate_x`, `translate_y`, `scale`,
`scale_x`, `scale_y`, `rotate`):

| Request | Result |
| --- | --- |
| `{"op": "set", "prop": p, "value": v}` | `null` (one Python-driven frame) |
| `{"op": "start", "id": n, "prop": p, "spec": {...}}` | `{"ok": true}` or `{"ok": false}` |
| `{"op": "cancel", "id": n}` | `{"value": presentation_value}` or `null` |

Specs are the dicts produced by `pn.Animated.timing`, `spring`, and
`decay`. Native reports completion through the callback with
`kind = "animation"` and payload `{"id": n, "finished": bool}`. Native
drives `timing` and `spring` on both platforms and `decay` on both
platforms, so the Python ticker is only used for callable easings,
per-frame listeners, and derived nodes.

## Native modules

A native module is a named object with methods. Python calls
`call(module, method, args_json)` where `args_json` is
`{"call_id": n, "args": {...}}`. The result is one of:

```json
{"ok": true, "value": ...}
{"ok": false, "error": "message", "code": "optional_code"}
{"pending": true}
```

`pending` means the method completes later; native then emits
`callback("module", 0, module, "{\"call_id\": n, \"ok\": true, \"value\": ...}")`.
Modules push unsolicited events with
`callback("module", 0, module, "{\"event\": \"change\", \"payload\": {...}}")`.

On the native side a module implements one method:

```swift
public final class ClipboardModule: PNNativeModule {
    public static let name = "Clipboard"
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "set_string": UIPasteboard.general.string = args["text"] as? String ?? ""; promise.resolve(nil)
        case "get_string": promise.resolve(UIPasteboard.general.string ?? "")
        default: promise.reject("unknown method \(method)")
        }
    }
}
```

If `promise` is resolved before `call` returns, the bridge answers
inline. If not, the bridge returns `pending` and delivers the result
when the promise settles. Kotlin modules implement the same shape
through `NativeModule.call(method, args, promise)`.

### Built-in modules

`Host`, `Device`, `Alert`, `Storage`, `SecureStore`, `Clipboard`,
`Share`, `Linking`, `Haptics`, `Battery`, `NetInfo`, `AppState`,
`Permissions`, `Notifications`, `Camera`, `Location`, `Biometrics`.

`Host` is special: it carries screen lifecycle and navigation
(`attach_root`, `detach_root`, `push`, `pop`, `pop_to_root`, `replace`,
`reset`, `set_options`, `viewport`). Native emits screen lifecycle to
Python through `callback("host", screen_id, event, payload_json)`;
`on_layout` and `on_resume` payloads carry `{"width", "height",
"insets": {"top", "left", "bottom", "right"}, "color_scheme"}` so
Python never has to query for them. `on_back_pressed` returns
`"true"` when a `use_back_handler` consumed the event.

### Python facades

Facades live in `pythonnative.native_modules` and are thin:

```python
from .registry import native_module

_clipboard = native_module("Clipboard")


class Clipboard:
    @staticmethod
    def set_string(text: str) -> None:
        _clipboard.call("set_string", text=text)

    @staticmethod
    def get_string() -> str:
        return str(_clipboard.call("get_string") or "")
```

`native_module` returns a `BridgeModule` on device and a registered
Python implementation on desktop and in tests. Desktop implementations
are plain classes with the same method names; built-ins register theirs
in `pythonnative.native_modules.fallback`, and packages register theirs
through the `pythonnative.modules` entry point group.

## Plugins

A PyPI package can ship native code alongside its Python facade. It
declares an entry point in the `pythonnative.plugins` group pointing at
a package directory that contains a `pn_plugin.json` manifest plus
`ios/` and `android/` source folders:

```toml
[project.entry-points."pythonnative.plugins"]
my_blur = "my_blur.native"
```

```json
{
  "ios": {"entry": "MyBlurPlugin"},
  "android": {"entry": "com.example.myblur.MyBlurPlugin"}
}
```

`pn build` copies `ios/*.swift` into `PythonNativeKit/Sources/Plugins`
and `android/**/*.kt` into the `pythonnative` module, then generates a
registration file that calls each entry's `register(_:)`. An entry
registers component managers and native modules:

```swift
public enum MyBlurPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("BlurView") { BlurViewManager() }
        registry.registerModule(BlurSettingsModule.self)
    }
}
```

Python-side element factories and typed props come from
`pythonnative.sdk`, exactly as for built-ins; tests use the
`ViewHandler` protocol for their off-device stand-ins.

## Protocol summary

```text
Python -> native      apply(transaction)         one call per commit
                      measure(tag, w, h)         synchronous intrinsic size
                      command(tag, name, args)   imperative view action
                      animate(tag, request)      animation set/start/cancel
                      call(module, method, args) native module method

native -> Python      callback("event",     tag,  name,   args_array)
                      callback("module",    0,    module, {call_id|event,...})
                      callback("host",      scr,  event,  payload)
                      callback("animation", 0,    "",     {id, finished})
                      callback("pump",      0,    "",     "")
```
