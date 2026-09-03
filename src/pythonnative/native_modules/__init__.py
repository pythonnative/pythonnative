"""Native API modules for device capabilities.

Cross-platform Python interfaces to common device APIs. Every module
here is a thin facade over a *native module*: a Swift class in
``PythonNativeKit`` and a Kotlin class in the ``pythonnative`` Gradle
module registered under the same name (``"Camera"``, ``"Haptics"``,
...). Facades reach them through
[`native_module`][pythonnative.native_modules.registry.native_module]
and the bridge described in ``docs/concepts/bridge.md``; there is no
Python-side Objective-C or JNI anywhere in this package.

On a desktop machine (``pn preview``, unit tests) the same names
resolve to plain Python implementations in
[`pythonnative.native_modules.desktop`][pythonnative.native_modules.desktop]
with safe defaults (in-memory buffers, ``"unknown"`` states, no-op
feedback), so the same code stays runnable off device. Third-party
packages ship their own native modules the same way; see
``docs/guides/native-modules.md``.

Hardware / media:

- [`Camera`][pythonnative.native_modules.Camera]: photo capture and
  gallery picking.
- [`Location`][pythonnative.native_modules.Location]: GPS and location.
- [`Battery`][pythonnative.native_modules.Battery]: charge level/state.
- [`Haptics`][pythonnative.native_modules.Haptics] /
  [`Vibration`][pythonnative.native_modules.Vibration]: tactile feedback.
- [`Biometrics`][pythonnative.native_modules.Biometrics]: Face ID /
  Touch ID / fingerprint auth.

System integration:

- [`FileSystem`][pythonnative.native_modules.FileSystem]: app-scoped
  file I/O.
- [`Notifications`][pythonnative.native_modules.Notifications]: local
  push notifications.
- [`Clipboard`][pythonnative.native_modules.Clipboard]: pasteboard
  read/write.
- [`Share`][pythonnative.native_modules.Share]: system share sheet.
- [`Linking`][pythonnative.native_modules.Linking]: open URLs and deep
  links.
- [`Permissions`][pythonnative.native_modules.Permissions]: runtime
  permission checks/requests.
- [`SecureStore`][pythonnative.native_modules.SecureStore]: encrypted
  secret storage.

Reactive state (with hooks):

- [`AppState`][pythonnative.native_modules.AppState] +
  [`use_app_state`][pythonnative.use_app_state]: foreground/background
  lifecycle.
- [`NetInfo`][pythonnative.native_modules.NetInfo] +
  [`use_net_info`][pythonnative.use_net_info]: connectivity.
"""

from .app_state import AppState, use_app_state
from .battery import Battery
from .biometrics import Biometrics
from .camera import Camera
from .clipboard import Clipboard
from .file_system import FileSystem
from .haptics import Haptics, Vibration
from .linking import Linking
from .location import Location
from .net_info import NetInfo, use_net_info
from .notifications import Notifications
from .permissions import Permissions
from .registry import (
    BridgeModule,
    NativeModule,
    NativeModuleError,
    PythonModule,
    native_module,
    register_python_module,
)
from .secure_store import SecureStore
from .share import Share

__all__ = [
    "AppState",
    "Battery",
    "Biometrics",
    "BridgeModule",
    "Camera",
    "Clipboard",
    "FileSystem",
    "Haptics",
    "Linking",
    "Location",
    "NativeModule",
    "NativeModuleError",
    "NetInfo",
    "Notifications",
    "Permissions",
    "PythonModule",
    "SecureStore",
    "Share",
    "Vibration",
    "native_module",
    "register_python_module",
    "use_app_state",
    "use_net_info",
]
