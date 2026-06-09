# Working with the E2E suite (for AI agents)

This document explains how an AI agent should interact with the PythonNative E2E test system. Read it before making changes that could affect any feature on the library's public surface, before adding a new feature, or when diagnosing a failing CI run.

## What this suite is

The E2E suite drives the `examples/e2e-suite` app on a real Android emulator or iOS Simulator using [Maestro](https://maestro.dev/). Every public symbol in `pythonnative.__all__` is either:

1. exercised by a dedicated demo screen + Maestro flow, or
2. listed in `INTENTIONAL_EXEMPTIONS` in `scripts/check-e2e-coverage.py` with a comment explaining why.

The coverage checker `scripts/check-e2e-coverage.py` enforces (1) and (2): if you add a new public symbol without adding a demo (or an exemption with justification), the script exits non-zero and CI fails.

## Map of the system

```text
examples/e2e-suite/
├── app/
│   ├── main.py                # Root Stack registers every demo route
│   ├── registry.py            # Single source of truth: DemoEntry list
│   ├── theme.py               # Shared styles used by every demo screen
│   └── screens/
│       ├── home.py            # Lists categories (anchor: "E2E Suite home")
│       ├── category.py        # Lists demos in a category (anchor: "Demos in <Cat>")
│       ├── scaffold.py        # demo_screen(...) helper used by every demo
│       ├── components/        # One file per Component demo
│       ├── hooks/             # One file per Hook demo
│       ├── navigation/        # One file per Navigation demo
│       ├── layout/            # Layout demos
│       ├── styling/           # Styling demos
│       ├── animations/        # Animated.* demos
│       ├── alerts/            # Alert.show / Alert.confirm demos
│       ├── storage/           # AsyncStorage demos
│       ├── runtime/           # run_async demo
│       ├── platform/          # Platform info demo
│       └── sdk/               # SDK surface demo
└── pythonnative.toml

tests/e2e/
├── AGENTS.md                  # (this file)
├── android.yaml               # Full Android suite — runs every flow
├── ios.yaml                   # Full iOS suite — runs every flow
├── helpers/
│   ├── open_demo.yaml         # Reusable: launch + nav to a demo
│   └── close_demo.yaml        # Reusable: pop back to home
├── suites/                    # Per-category aggregator yamls
│   ├── components.yaml
│   ├── hooks.yaml
│   └── ...
└── flows/                     # One yaml per demo
    ├── components/
    ├── hooks/
    └── ...

scripts/
├── run-e2e.sh                 # Build app + run a Maestro suite
└── check-e2e-coverage.py      # Static check; mirrors __all__ to demos
```

## Running the suite locally

```bash
# Full Android suite (emulator must be running)
./scripts/run-e2e.sh android

# Full iOS suite (simulator must be running; idb-companion installed)
./scripts/run-e2e.sh ios

# Just one category, for tight iteration loops:
./scripts/run-e2e.sh android hooks
./scripts/run-e2e.sh ios components
```

Available category suites: `components`, `hooks`, `navigation`, `layout`, `styling`, `animations`, `misc`.

You can also run a single flow directly. Useful when iterating on one demo:

```bash
maestro test \
  -e APP_ID=com.pythonnative.e2e \
  tests/e2e/flows/hooks/use_state.yaml
```

The build step (`pn run <platform> --no-logs`) only needs to run once per change to `app/`. After that, repeat-run the Maestro flow as you iterate.

### How `open_demo.yaml` decides what to do

`helpers/open_demo.yaml` is *state-aware* — it inspects the current screen and runs only the steps it needs to land on `Demo: <DEMO_TITLE>`. Same-category consecutive flows stay on the category screen between demos (no detour through home, no `launchApp`); cross-category transitions go via home; a dead app gets relaunched. The companion `helpers/close_demo.yaml` only pops one level (back to the category list) so the next flow's `open_demo` can pick up cheaply.

This is intentional and the source of the suite's speed. When debugging a flow, **don't** "simplify" `open_demo` to always `launchApp` + go home + go to category — that's the slow path the smart logic was written to avoid (about 15 min vs. 3 min of pure navigation overhead across the full iOS suite). If a flow needs a guaranteed clean app launch, set up that state in the flow itself.

Gate conditions in `open_demo` deliberately use signals that work on **both** platforms. The two cross-platform asymmetries that matter here:

- **Scroll preservation.** iOS preserves a ScrollView's offset across navigation; Android resets it to the top. A condition like `visible: "Back to home"` (button at the bottom of a category list) works on iOS after a return-from-demo but fails on Android because the list is back at the top. The helper gates on `"Demos in .*"` (top of the list, visible on both) and `notVisible: "Back to list"` (i.e. we left the demo screen) instead.
- **Native-view recreation on Android.** The Android FragmentManager destroys and rebuilds a screen's view tree on pop-back; `pythonnative.screen._on_create` short-circuits the second call so hook state, `use_focus_effect` subscriptions, and `use_navigation` handles persist. If a future change to `screen.py` or `ScreenFragment.kt` breaks that idempotency, `flows/navigation/focus_effect.yaml` is the canary — it'll regress to `Focus count: 1` on pop-back.

### Scrolling fixed-height containers (ScrollView / FlatList)

Maestro's `scrollUntilVisible` always swipes from the screen center. That works for the outer page ScrollView (which fills the screen) but **not** for small in-page containers like the 200 dp `ScrollView` / `FlatList` demos — the screen center sits below those containers, so the swipe lands outside them and never moves the contents.

`flows/components/scroll_view.yaml` and `flows/components/flat_list.yaml` work around this with an explicit-coordinate swipe loop wrapped in `repeat: while: notVisible: ...`. Two reasons for the loop rather than a fixed `times: N`:

- Per-swipe scroll travel is platform-dependent — Android's `NestedScrollView` flings more aggressively than iOS's `UIScrollView`, so a count tuned for one platform overshoots on the other.
- iOS preserves the inner ScrollView's offset across navigation, so a re-entry into the demo may already have the target row in view; `while: notVisible` exits the loop immediately in that case.

When adding a new flow that needs to scroll a non-fullscreen container, copy this pattern (small swipes ~10% of screen height, ~500 ms each, `times` cap as a safety net) rather than calling `scrollUntilVisible`.

### Suite-level retry

`scripts/run-e2e.sh` re-invokes the whole `maestro test` once if the first attempt exits non-zero. The retry exists to absorb Maestro's iOS XCUITest driver flake (transient `Application is not running` / `Request for viewHierarchy failed`) — not to paper over real failures.

When the script prints:

```text
==> Maestro suite failed (attempt 1/2); retrying...
```

treat it as a signal to investigate, not as "all clear." If a flow needs the retry to pass on a given run, the underlying issue is almost always one of:

- a genuine race or timing assumption in the demo or flow (fix it),
- a CPU-starvation-induced numerical instability in animated code (clamp the integrator),
- or a real Maestro/driver bug worth filing upstream.

Override or disable with `MAESTRO_MAX_ATTEMPTS=1 ./scripts/run-e2e.sh ios` when bisecting a flake.

## The flow header convention

Every flow file under `tests/e2e/flows/` starts with a two-line header pointing at the demo and the source code:

```yaml
# Tests <one-line summary of what's verified>.
#
# Demo screen: examples/e2e-suite/app/screens/<category>/<file>.py
# Source under test: src/pythonnative/<file>.py :: <symbol>
appId: ${APP_ID}
---
```

When a flow fails, **start by reading these three files in order**:

1. The flow yaml — see what assertion failed.
2. The demo screen — see what the demo expected to render.
3. The source under test — see the implementation that's responsible.

## When a flow fails

A typical Maestro failure looks like:

```text
[Failed] hooks/use_state.yaml
  Assertion 'Counter: 2' not visible after 10s.
```

Diagnostic procedure:

1. **Locate the flow file**: `tests/e2e/flows/hooks/use_state.yaml`.
2. **Read the header comment** to find the demo screen (`use_state.py`) and the source file (`hooks.py :: use_state`).
3. **Re-run the single flow** to confirm the failure is reproducible:

   ```bash
   maestro test -e APP_ID=com.pythonnative.e2e tests/e2e/flows/hooks/use_state.yaml
   ```

4. **Inspect logs**: `pn run android` streams `print()` calls from the device. `print("[use_state] count -> ...")` style debug statements from the demo screen surface here, which is usually the fastest way to localize a regression.
5. **Reproduce in isolation**: many failures are state-related. Re-run `./scripts/run-e2e.sh android components` (or the relevant category) — if the flow passes there but fails in the full suite, the bug is most likely in cleanup between flows.

## Adding a new demo (and its flow)

When you add a new public symbol to `pythonnative`, follow this exact recipe:

1. Add an exported name to `src/pythonnative/__init__.py :: __all__`.
2. Implement the feature.
3. Create the demo screen at `examples/e2e-suite/app/screens/<category>/<symbol>.py`:

   ```python
   import pythonnative as pn
   from app.screens.scaffold import demo_screen, hint, result_text, section


   @pn.component
   def MyFeatureDemo() -> pn.Element:
       return demo_screen(
           "My feature",
           "Short summary visible on the demo screen.",
           section(
               "Try it",
               result_text("State", "..."),
               pn.Button("Trigger", on_click=lambda: None),
               hint("Maestro asserts the State line."),
           ),
       )
   ```

4. Register the demo in `examples/e2e-suite/app/registry.py`:

   ```python
   from app.screens.<category>.<symbol> import MyFeatureDemo

   DEMOS = [
       ...
       DemoEntry("my_feature", "Hooks", "My feature", "<symbol>", MyFeatureDemo),
   ]
   ```

5. Author the Maestro flow at `tests/e2e/flows/<category>/<symbol>.yaml`. Use the existing flows as templates; they all use the `open_demo.yaml` / `close_demo.yaml` helpers.
6. Append the new flow to:
   - `tests/e2e/android.yaml`
   - `tests/e2e/ios.yaml`
   - `tests/e2e/suites/<category>.yaml`
7. Run `python scripts/check-e2e-coverage.py` and confirm it exits 0.
8. Run `./scripts/run-e2e.sh android` (or `ios`) and confirm the new flow passes.

If a symbol is genuinely untestable through a UI flow (type-only alias, network-dependent, requires hardware), instead add it to `INTENTIONAL_EXEMPTIONS` in `scripts/check-e2e-coverage.py` with a comment explaining why.

## Stable label conventions

These conventions keep flows robust across platforms. Stick to them when authoring demo screens.

| Where the label appears | Format | Example |
| --- | --- | --- |
| Home screen anchor | exact text | `"E2E Suite home"` |
| Home category button | `"Open <Category>"` | `"Open Hooks"` |
| Category screen anchor | `"Demos in <Category>"` | `"Demos in Hooks"` |
| Category demo button | `"Open: <Title>"` | `"Open: use_state"` |
| Demo screen anchor | `"Demo: <Title>"` | `"Demo: use_state"` |
| Result line | `"<Prefix>: <Value>"` | `"Counter: 2"` |
| Back button | `"Back to list"` | (same on every demo) |

Avoid emoji and platform-specific glyphs in labels — Maestro's text matching is much happier with plain ASCII.

## When tests fail because the demo, not the library, is wrong

It happens. The fix is to update the flow + demo together so the test reflects intended behavior. Do NOT:

- mark a flow as `flaky` or wrap it in retries without first finding the root cause,
- change a `result_text` value to silence the test if the library returns something genuinely incorrect,
- delete a flow because it's hard to fix on one platform — gate it with `runFlow` from one of the platform-specific suites instead (we don't have these yet, but `flows/<category>/<feature>_android.yaml` is the established naming if needed).

When you do change a demo or flow, update its header comment so it still accurately documents what's being tested.

## CI integration

The full suite runs on every push to `main` and every PR via `.github/workflows/e2e.yml`. Both the Android job (Linux runner + emulator) and the iOS job (macOS runner + simulator) call into `scripts/run-e2e.sh`, so the local and CI execution paths are identical.

The coverage check is wired into `scripts/check.sh`, which `ci.yml` runs on every push and PR. New `__all__` entries without a demo (or exemption) fail CI before the E2E job even starts, which keeps the inner loop fast.
