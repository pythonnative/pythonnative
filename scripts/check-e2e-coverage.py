#!/usr/bin/env python3
"""Verify every public ``pythonnative`` symbol is exercised by an E2E demo.

Run as part of ``./scripts/check.sh`` or directly:

    python scripts/check-e2e-coverage.py

The script:

1. Reads ``pythonnative.__all__`` to get the list of public symbols.
2. Reads ``examples/e2e-suite/app/registry.py`` to discover every
   demo's ``feature`` field. Each ``feature`` either matches a name
   in ``__all__`` or uses a ``"category::name"`` form for sub-features
   that aren't directly listed.
3. Reports any public symbol not covered by at least one demo.
4. Reports any demo flow file missing for a registered demo.

Exit code is ``0`` when every public symbol is covered and every demo
has a matching flow file; ``1`` otherwise.

This script is *static analysis only*: it doesn't run the app or the
flows. It exists so that adding a new public export to ``pythonnative``
without adding an E2E demo is a CI failure rather than a silent
regression.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Set

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pythonnative" / "__init__.py"
REGISTRY = ROOT / "examples" / "e2e-suite" / "app" / "registry.py"
FLOWS_DIR = ROOT / "tests" / "e2e" / "flows"

# Symbols intentionally NOT covered by a directly-mapped E2E flow.
# Each entry has a comment explaining why the symbol is exempt: type
# alias, ambient infrastructure exercised by every flow, or platform
# capability that requires real device hardware. New entries should
# justify themselves in the same way.
INTENTIONAL_EXEMPTIONS: Set[str] = {
    # --------------------------------------------------------------
    # Type-only re-exports — statically checkable, no UI surface.
    # --------------------------------------------------------------
    "Element",
    "AlignItems",
    "AlignSelf",
    "AutoCapitalize",
    "Color",
    "Dimension",
    "EdgeInsets",
    "FlexDirection",
    "FontWeight",
    "JustifyContent",
    "KeyboardType",
    "Overflow",
    "Position",
    "ReturnKeyType",
    "ScaleType",
    "ShadowOffset",
    "Style",
    "StyleProp",
    "TextAlign",
    "TextDecoration",
    "ThemeContext",
    "TransformSpec",
    "AnimatedValue",  # observed via use_animated_value usage in animations
    "QueryResult",  # observed via use_query demo
    "MutationCall",  # observed via use_mutation demo
    "MutationState",  # observed via use_mutation demo
    # --------------------------------------------------------------
    # Built-in Props dataclasses — exercised indirectly via their
    # corresponding component demos.
    # --------------------------------------------------------------
    "ActivityIndicatorProps",
    "ButtonProps",
    "CheckboxProps",
    "DatePickerProps",
    "ImageBackgroundProps",
    "ImageProps",
    "KeyboardAvoidingViewProps",
    "ModalProps",
    "PickerProps",
    "PressableProps",
    "ProgressBarProps",
    "SafeAreaViewProps",
    "ScrollViewProps",
    "SegmentedControlProps",
    "SliderProps",
    "SpacerProps",
    "StatusBarProps",
    "SwitchProps",
    "TextInputProps",
    "TextProps",
    "TouchableOpacityProps",
    "ViewProps",
    "WebViewProps",
    # --------------------------------------------------------------
    # Ambient infrastructure exercised by every flow (importing the
    # app + rendering any screen invokes them, so a dedicated demo
    # would be redundant).
    # --------------------------------------------------------------
    "component",  # @pn.component decorator — every screen uses it
    "Column",  # used everywhere; co-tested with View in ViewColumnRowDemo
    "Row",  # used everywhere; co-tested with View in ViewColumnRowDemo
    "NavigationContainer",  # wraps the root navigator; used by main.py
    "create_stack_navigator",  # used by main.py; every flow pushes screens
    "create_screen",  # platform bridge invoked by the native templates
    "use_navigation",  # used by every screen for go_back
    "use_animated_value",  # used in every animation demo
    "Provider",  # covered by use_context demo
    "create_context",  # covered by use_context demo
    "style",  # the style helper itself is exercised by every styled demo
    "resolve_style",  # internal helper exposed for SDK authors
    # --------------------------------------------------------------
    # Hooks whose values depend on physical device state that an
    # emulator/simulator can't reliably reproduce.
    # --------------------------------------------------------------
    "use_safe_area_insets",  # no reliable insets in emulator viewport
    "use_keyboard_height",  # requires a real keyboard transition
    "use_app_state",  # requires backgrounding the app (device lifecycle)
    "use_net_info",  # requires toggling real connectivity
    # --------------------------------------------------------------
    # Networking + native-module surfaces. These need network or
    # platform hardware (camera, location, notifications, clipboard,
    # haptics, biometrics, …) that CI emulators don't reliably
    # provide; tested via unit tests in tests/test_net.py and
    # tests/test_native_modules.py against their desktop fallbacks.
    # --------------------------------------------------------------
    "fetch",
    "HTTPError",
    "Response",
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
    # --------------------------------------------------------------
    # SDK re-exports — module-level names mirroring submodule content.
    # --------------------------------------------------------------
    "runtime",  # module re-export; run_async demo covers it
    "sdk",  # module re-export; custom_component demo covers it
    "ViewHandler",  # ABC; subclassed by built-in handlers
    "element_factory",  # tested via unit tests; needs registered handlers
    "register_component",  # tested via unit tests; needs handler implementations
    "Props",  # tested in custom_component demo and SDK unit tests
}


def _public_symbols() -> Set[str]:
    """Return the values of ``__all__`` in the pythonnative package.

    Parsed via ``ast`` rather than imported, so the check can run
    without instantiating the package (which would pull in iOS/Android
    code paths that fail off-device).
    """
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        names: Set[str] = set()
                        for el in node.value.elts:
                            if isinstance(el, ast.Constant) and isinstance(el.value, str):
                                names.add(el.value)
                        return names
    raise RuntimeError(f"No __all__ list found in {SRC}")


def _read_registry_features() -> Set[str]:
    text = REGISTRY.read_text(encoding="utf-8")
    # Match: DemoEntry("id", "Category", "Title", "feature", ComponentName),
    pattern = re.compile(
        r'DemoEntry\(\s*"(?P<id>[^"]+)"\s*,\s*"(?P<category>[^"]+)"\s*,'
        r'\s*"(?P<title>[^"]+)"\s*,\s*"(?P<feature>[^"]+)"\s*,',
        re.MULTILINE,
    )
    return {m.group("feature") for m in pattern.finditer(text)}


def _read_registry_ids() -> Set[str]:
    text = REGISTRY.read_text(encoding="utf-8")
    pattern = re.compile(r'DemoEntry\(\s*"(?P<id>[^"]+)"', re.MULTILINE)
    return {m.group("id") for m in pattern.finditer(text)}


def _flow_files() -> Set[str]:
    """Return the set of demo ids that have a flow file."""
    ids: Set[str] = set()
    for path in FLOWS_DIR.rglob("*.yaml"):
        # Flow filename is the demo id (e.g. ``use_state.yaml``).
        ids.add(path.stem)
    return ids


def _format_report(
    public: Iterable[str],
    features: Set[str],
    demo_ids: Set[str],
    flow_ids: Set[str],
) -> dict:
    public_set = set(public)
    direct_covered = features & public_set
    missing_public = public_set - features - INTENTIONAL_EXEMPTIONS
    missing_flows = demo_ids - flow_ids
    extra_flows = flow_ids - demo_ids
    return {
        "public_symbols": len(public_set),
        "demos": len(demo_ids),
        "flows": len(flow_ids),
        "directly_covered_public_symbols": sorted(direct_covered),
        "missing_public_symbols": sorted(missing_public),
        "demos_without_flow": sorted(missing_flows),
        "flow_files_without_demo": sorted(extra_flows),
    }


def main(argv: list[str]) -> int:
    """Run the coverage check and print a human or JSON report."""
    public = _public_symbols()
    features = _read_registry_features()
    demo_ids = _read_registry_ids()
    flow_ids = _flow_files()

    report = _format_report(public, features, demo_ids, flow_ids)

    json_mode = "--json" in argv
    if json_mode:
        print(json.dumps(report, indent=2))
    else:
        print("E2E coverage report")
        print("===================")
        print(f"  Public symbols in pythonnative.__all__: {report['public_symbols']}")
        print(f"  Demo entries in registry:               {report['demos']}")
        print(f"  Flow files under tests/e2e/flows:       {report['flows']}")
        print(f"  Public symbols directly covered:        {len(report['directly_covered_public_symbols'])}")
        print(f"  Intentional exemptions:                 {len(INTENTIONAL_EXEMPTIONS)}")
        if report["missing_public_symbols"]:
            print()
            print("  ERROR: the following public symbols have no E2E demo:")
            for name in report["missing_public_symbols"]:
                print(f"    - {name}")
            print()
            print(
                "  Fix: add a DemoEntry to examples/e2e-suite/app/registry.py "
                'with feature="<name>", create the screen, and add a '
                "tests/e2e/flows/<category>/<id>.yaml file.\n"
                "  Alternatively, if the symbol genuinely can't be tested "
                "via a UI flow, add it to INTENTIONAL_EXEMPTIONS in this "
                "script with a justification comment."
            )
        if report["demos_without_flow"]:
            print()
            print("  ERROR: the following registered demos have no flow file:")
            for name in report["demos_without_flow"]:
                print(f"    - {name}")
        if report["flow_files_without_demo"]:
            print()
            print("  WARNING: the following flow files don't match any registered demo:")
            for name in report["flow_files_without_demo"]:
                print(f"    - {name}")

    failed = bool(report["missing_public_symbols"]) or bool(report["demos_without_flow"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
