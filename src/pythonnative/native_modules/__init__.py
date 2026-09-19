"""Native API modules for device capabilities.

Cross-platform Python interfaces to common device APIs. Every module
here is a thin facade over a *native module*: a Swift class in
``PythonNativeKit`` and a Kotlin class in the ``pythonnative`` Gradle
module registered under the same name (``"Camera"``, ``"Haptics"``,
...). Facades reach them through
[`native_module`][pythonnative.native_modules.registry.native_module]
and the bridge described in ``docs/concepts/bridge.md``; there is no
Python-side Objective-C or JNI anywhere in this package.

Off device the same names resolve to plain Python implementations in
[`pythonnative.native_modules.fallback`][pythonnative.native_modules.fallback]
with safe defaults (in-memory buffers, ``"unknown"`` states, no-op
feedback), so the same code stays runnable in unit tests. The browser
preview (``pn start``) implements the modules a browser can honor
(``Alert``, ``Clipboard``, ``Device``, ``Linking``, ``Share``, ...) in
the page and falls back to the Python classes for the rest. Third-party
packages ship their own native modules the same way; see
``docs/guides/native-modules.md``.

Two rules hold across every facade, so you never have to look one up:

1. **Sync or async is decided by what the OS has to do.** A method is
   a plain function when the answer is already on the device and
   returns on the calling thread (read the pasteboard, check a
   permission, read the battery level, Keychain get/set, file I/O).
   It is a coroutine when the OS has to prompt the user, drive
   hardware, or hand off to another process (camera and gallery
   pickers, biometric prompts, permission requests, the share sheet,
   GPS fixes, notification scheduling, remote push registration).
2. **Failures raise; "nothing happened" returns a value.** A native
   error (a rejected promise, a missing module, a bad argument) is a
   [`NativeModuleError`][pythonnative.native_modules.NativeModuleError]
   and propagates to the caller like any other Python exception. Outcomes
   that are not errors, such as the user cancelling a picker, denying a
   permission, or dismissing the share sheet, come back as ``None``,
   ``False``, or a status string, and are documented per method. No
   facade converts an exception into a default value.

Hardware / media:

- [`Camera`][pythonnative.native_modules.Camera]: photo capture and
  gallery picking.
- [`Location`][pythonnative.native_modules.Location]: GPS and location.
- [`Battery`][pythonnative.native_modules.Battery]: charge level/state.
- [`Haptics`][pythonnative.native_modules.Haptics] /
  [`Vibration`][pythonnative.native_modules.Vibration]: tactile feedback.
- [`Biometrics`][pythonnative.native_modules.Biometrics]: Face ID /
  Touch ID / fingerprint auth.

Device and environment:

- [`Device`][pythonnative.native_modules.Device]: static device and app
  facts as a [`DeviceInfo`][pythonnative.native_modules.DeviceInfo].
- [`Dimensions`][pythonnative.native_modules.Dimensions] /
  [`PixelRatio`][pythonnative.native_modules.PixelRatio]: window and
  screen size, density, and pixel rounding.
- [`Keyboard`][pythonnative.native_modules.Keyboard]: keyboard
  visibility, dismissal, and transitions.
- [`Localization`][pythonnative.native_modules.Localization] +
  [`use_locales`][pythonnative.use_locales]: preferred locales, layout
  direction, and time zone.
- [`AccessibilityInfo`][pythonnative.native_modules.AccessibilityInfo] +
  [`use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled] /
  [`use_reduce_motion`][pythonnative.use_reduce_motion]: screen-reader
  and reduce-motion state, announcements, focus.

System integration:

- [`FileSystem`][pythonnative.native_modules.FileSystem]: app-scoped
  file I/O.
- [`Images`][pythonnative.native_modules.Images]: measure, prefetch,
  and clear cached images (bundled, local, or remote).
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

from .accessibility_info import AccessibilityEvent, AccessibilityInfo, use_reduce_motion, use_screen_reader_enabled
from .app_state import AppState, use_app_state
from .battery import Battery
from .biometrics import Biometrics
from .camera import Camera
from .clipboard import Clipboard
from .device import Device, DeviceInfo
from .dimensions import Dimensions, DimensionsEvent, PixelRatio
from .file_system import FileSystem
from .haptics import Haptics, Vibration
from .images import Images, ImageSize
from .keyboard import Keyboard, KeyboardEvent
from .linking import Linking
from .localization import Locale, Localization, use_locales
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
    "AccessibilityEvent",
    "AccessibilityInfo",
    "AppState",
    "Battery",
    "Biometrics",
    "BridgeModule",
    "Camera",
    "Clipboard",
    "Device",
    "DeviceInfo",
    "Dimensions",
    "DimensionsEvent",
    "FileSystem",
    "Haptics",
    "ImageSize",
    "Images",
    "Keyboard",
    "KeyboardEvent",
    "Linking",
    "Locale",
    "Localization",
    "Location",
    "NativeModule",
    "NativeModuleError",
    "NetInfo",
    "Notifications",
    "Permissions",
    "PixelRatio",
    "PythonModule",
    "SecureStore",
    "Share",
    "Vibration",
    "native_module",
    "register_python_module",
    "use_app_state",
    "use_locales",
    "use_net_info",
    "use_reduce_motion",
    "use_screen_reader_enabled",
]
