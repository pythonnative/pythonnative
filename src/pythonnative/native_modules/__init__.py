"""Native API modules for device capabilities.

Provides cross-platform Python interfaces to common device APIs. Each
module auto-detects the platform at import time and dispatches to the
appropriate native APIs via Chaquopy (Android) or rubicon-objc (iOS).
On a desktop machine without either runtime, modules fall back to safe
defaults (in-memory buffers, ``"unknown"`` states, no-op feedback) so
the same code stays runnable in the desktop mock and unit tests.

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
from .secure_store import SecureStore
from .share import Share

__all__ = [
    "AppState",
    "Battery",
    "Biometrics",
    "Camera",
    "Clipboard",
    "FileSystem",
    "Haptics",
    "Linking",
    "Location",
    "NetInfo",
    "Notifications",
    "Permissions",
    "SecureStore",
    "Share",
    "Vibration",
    "use_app_state",
    "use_net_info",
]
