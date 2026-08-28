from pythonnative.project.devices import (
    Device,
    find_device,
    parse_adb_devices,
    parse_devicectl_devices,
    parse_simctl_devices,
)

_ADB_OUTPUT = """List of devices attached
emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emu64a transport_id:1
R5CT30XXXX             device usb:1-1 product:beyond1 model:SM_G973F device:beyond1 transport_id:2
0A1B2C3D               unauthorized transport_id:3
"""

_SIMCTL_PAYLOAD = {
    "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-17-5": [
            {"udid": "AAAA-1111", "name": "iPhone 15", "state": "Booted", "isAvailable": True},
            {"udid": "BBBB-2222", "name": "iPhone 15 Pro", "state": "Shutdown", "isAvailable": True},
            {"udid": "CCCC-3333", "name": "Broken", "state": "Shutdown", "isAvailable": False},
        ],
        "com.apple.CoreSimulator.SimRuntime.watchOS-10-0": [
            {"udid": "DDDD-4444", "name": "Apple Watch", "state": "Shutdown", "isAvailable": True},
        ],
    }
}

_DEVICECTL_PAYLOAD = {
    "result": {
        "devices": [
            {
                "identifier": "EEEE-5555",
                "deviceProperties": {"name": "Owen's iPhone", "osVersionNumber": "17.5.1"},
                "hardwareProperties": {"marketingName": "iPhone 15 Pro"},
                "connectionProperties": {"tunnelState": "connected"},
            },
            {
                "identifier": "FFFF-6666",
                "deviceProperties": {"name": "Old iPad"},
                "hardwareProperties": {},
                "connectionProperties": {"tunnelState": "disconnected"},
            },
        ]
    }
}


def test_parse_adb_devices() -> None:
    devices = parse_adb_devices(_ADB_OUTPUT)
    assert len(devices) == 3
    emulator, phone, locked = devices
    assert emulator.kind == "emulator"
    assert emulator.identifier == "emulator-5554"
    assert emulator.state == "connected"
    assert phone.kind == "device"
    assert phone.name == "SM G973F"
    assert locked.state == "offline"
    assert not locked.is_ready


def test_parse_simctl_devices_filters_and_versions() -> None:
    devices = parse_simctl_devices(_SIMCTL_PAYLOAD)
    # watchOS runtimes and unavailable simulators are excluded.
    assert {d.name for d in devices} == {"iPhone 15", "iPhone 15 Pro"}
    booted = next(d for d in devices if d.name == "iPhone 15")
    assert booted.state == "booted"
    assert booted.os_version == "iOS 17.5"
    assert booted.kind == "simulator"
    assert booted.is_ready


def test_parse_devicectl_devices() -> None:
    devices = parse_devicectl_devices(_DEVICECTL_PAYLOAD)
    assert len(devices) == 2
    connected, offline = devices
    assert connected.identifier == "EEEE-5555"
    assert connected.name == "Owen's iPhone"
    assert connected.os_version == "iOS 17.5.1"
    assert connected.state == "connected"
    assert offline.state == "offline"


def test_find_device_by_identifier_name_and_substring() -> None:
    devices = parse_simctl_devices(_SIMCTL_PAYLOAD) + parse_devicectl_devices(_DEVICECTL_PAYLOAD)
    assert find_device(devices, "BBBB-2222").name == "iPhone 15 Pro"
    assert find_device(devices, "owen's iphone").identifier == "EEEE-5555"
    assert find_device(devices, "ipad").identifier == "FFFF-6666"
    assert find_device(devices, "nope") is None
    # Exact-name matches prefer ready devices; "iPhone 15" is booted.
    assert find_device(devices, "iPhone 15").state == "booted"


def test_find_device_prefers_ready() -> None:
    devices = [
        Device(platform="android", kind="device", identifier="one", name="Pixel", state="offline"),
        Device(platform="android", kind="device", identifier="two", name="Pixel", state="connected"),
    ]
    assert find_device(devices, "Pixel").identifier == "two"
