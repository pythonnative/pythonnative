# Biometrics

Gate an action behind Face ID, Touch ID, or a fingerprint.

## Setup

```toml
[plugins]
use = ["biometrics"]

[permissions]
face_id = "Unlock your vault."
```

## Usage

```python
from pythonnative.biometrics import Biometrics


async def unlock() -> None:
    if Biometrics.is_available() and await Biometrics.authenticate("Unlock your vault"):
        show_secrets()
```

`authenticate` resolves `False` when the user fails or cancels, and a failure of the prompt itself raises `NativeModuleError`.

## Platform differences

- iOS falls back to the device passcode when biometrics aren't enrolled. Android reports `False` instead.
- Android uses `BiometricPrompt` at the `BIOMETRIC_WEAK` level.
- The browser preview and tests report no hardware.

## What wasn't verified

Simulators have no enrolled biometrics by default, so CI proves only that the capability answers. Try the prompt on a device.
