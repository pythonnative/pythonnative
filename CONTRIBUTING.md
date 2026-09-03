### Contributing to PythonNative

Thanks for your interest in contributing. This repository contains the PythonNative library, the `pn` CLI, Android/iOS project templates, example apps, and the documentation site. Contributions should keep the code reliable, cross-platform, and easy to use.

## Quick start

Development uses Python ≥ 3.13 (the same versions the apps embed) and [uv](https://docs.astral.sh/uv/) as the
only prerequisite. `uv sync` creates and updates `.venv` itself, so there's no
virtual environment to make and nothing to activate.

```bash
# install the project and its dev tooling into .venv, exactly as CI does
uv sync --locked --group dev

# one-shot: runs every CI check, in the same order
./scripts/check.sh

# run individual steps if you only want one
uv run pytest -q
uv run ruff check .
uv run black src examples tests
```

Dependencies are pinned in `uv.lock`, which is committed, so local runs and CI
resolve identically. `--locked` fails rather than silently re-resolving if the
lockfile has drifted from `pyproject.toml`. Upgrading a dependency is a
deliberate `uv lock --upgrade-package <name>` in its own commit.

Common library and CLI entry points. `uv run` puts `.venv/bin` on the path
for one command, so `pn` resolves without activating anything. Each block
starts from the repository root.

```bash
# CLI help
uv run pn --help

# scaffold a sample app into ./my_app/, then work inside it
uv run pn init my_app
cd my_app
uv run pn run android
```

`uv run` looks upward for the nearest project, so it keeps using the
repository's `.venv` from a subdirectory. The bundled example works the same
way:

```bash
# run the Hello World example
cd examples/hello-world && uv run pn run android
```

## Claiming an issue

To avoid duplicate work, claim an issue before you start on it:

1. Check the issue's assignee and any linked pull requests. If either exists, the issue is taken.
2. Comment on the issue to claim it and wait for a maintainer to assign it to you before opening a pull request.
3. If you stop working on an assigned issue, leave a comment so it can be reassigned.

Unsolicited pull requests for issues that are already assigned or already have an open pull request will be closed as duplicates, even if the work is good.

## Project layout (high‑level)

- `src/pythonnative/`: installable library and CLI
  - `pythonnative/`: core cross‑platform UI components and utilities
  - `bridge/`: JSON codec and per-platform transports into the native rendering core
  - `cli/`: `pn` command
  - `project/`: config loading, template configuration, native plugin staging, and the builder behind `pn`
  - `templates/`: Android/iOS project templates (bundled with the package)
    - `ios_template/PythonNativeKit/`: Swift package with the iOS rendering core (component managers, gestures, animations, native modules) and its XCTest target
    - `android_template/pythonnative/`: Gradle library module with the Android rendering core and its JUnit target
- `tests/`: unit tests for the library, plus the Maestro E2E suite
  - `e2e/`: the comprehensive E2E suite (see [E2E tests](#e2e-tests-maestro) below and `tests/e2e/AGENTS.md`)
- `examples/`: runnable example apps
  - `hello-world/`: minimal marketing demo
  - `e2e-suite/`: comprehensive feature catalog that drives the Maestro E2E suite
- `scripts/`: helper scripts (`check.sh`, `run-e2e.sh`, `check-e2e-coverage.py`)
- `README.md`, `pyproject.toml`: repo docs and packaging

## Coding guidelines

- Style: Black; lint: Ruff; typing where useful. Keep APIs stable.
- Prefer explicit, descriptive names; keep platform abstractions clean.
- Python never imports platform code. Everything that touches `UIView` or `android.view.View` lives in Swift (`PythonNativeKit`) or Kotlin (the `pythonnative` Gradle module) and is reached through `pythonnative.bridge`; see `docs/concepts/bridge.md` for the protocol. Bump `PROTOCOL_VERSION` on both sides when the wire format changes.
- Add/extend tests under `tests/` for new behavior. Native changes get XCTest / JUnit coverage next to the code they touch.
- Don't commit generated artifacts or large binaries; templates live under `src/pythonnative/templates/`.
- Docstrings: Google style throughout. Ruff is configured with the Google
  convention (`pydocstyle.convention = "google"`) and enforces the `D` rule
  set on `src/pythonnative/`. See the
  [Documentation style guide](https://pythonnative.com/meta/style-guide/)
  for examples and Markdown/grammar conventions.

Common commands:

```bash
./scripts/check.sh              # run all CI checks (mirrors ci.yml)
uv sync --locked --group dev    # install/refresh .venv from the lockfile
uv run pytest -q                # run tests
uv run ruff check .             # lint
uv run black src examples tests # format
uv run --group docs mkdocs serve # preview the docs site locally

# native rendering core (macOS with Xcode for the Swift package; JDK 17 for Gradle)
(cd src/pythonnative/templates/ios_template/PythonNativeKit && xcodebuild test -scheme PythonNativeKit -destination 'platform=iOS Simulator,name=iPhone 15 Pro')
(cd src/pythonnative/templates/android_template && ./gradlew :pythonnative:testDebugUnitTest)
```

## Conventional Commits

This project uses Conventional Commits. Use the form:

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### Commit message character set

- Encoding: UTF‑8 is allowed and preferred across subjects and bodies.
- Keep the subject ≤ 72 chars; avoid emoji.

Accepted types (standard):

- `build`: build system or external dependencies (e.g., requirements, packaging)
- `chore`: maintenance (no library behavior change)
- `ci`: continuous integration configuration (workflows, pipelines)
- `docs`: documentation only
- `feat`: user‑facing feature or capability
- `fix`: bug fix
- `perf`: performance improvements
- `refactor`: code change that neither fixes a bug nor adds a feature
- `revert`: revert of a previous commit
- `style`: formatting/whitespace (no code behavior)
- `test`: add/adjust tests only

Recommended scopes (choose the smallest, most accurate unit; prefer module/directory names):

- Module/directory scopes:
  - `alerts`: imperative Alert/Picker helpers (`alerts.py`)
  - `animated`: Animated namespace and animation primitives (`animated.py`)
  - `bootstrap`: on-device runtime start-up called by the templates (`bootstrap.py`)
  - `bridge`: wire codec, transports, handshake, and native-to-Python callback (`bridge/`)
  - `cli`: CLI tool and `pn` command (`src/pythonnative/cli/`)
  - `component`: the `@component` decorator, `Component`, and `memo` (`component.py`)
  - `components`: declarative element-creating functions (`components/`)
  - `element`: Element descriptor class (`element.py`)
  - `events`: tag-based event routing between native views and Python callbacks (`events.py`)
  - `gestures`: gesture descriptors and the pure-Python recognition arbiter (`gestures.py`)
  - `hooks`: hooks and contexts (`hooks.py`)
  - `hosts`: screen hosts, lifecycle forwarding, and render scheduling (`hosts/`)
  - `hot_reload`: file watcher and module reloader (`hot_reload.py`)
  - `layout`: pure-Python flexbox engine (`layout.py`)
  - `mutations`: batched mutation ops between reconciler and native backends (`mutations.py`)
  - `native_modules`: native module registry, Python facades, and desktop implementations (`native_modules/`)
  - `native_views`: view registry protocol, bridge backend, and desktop handlers (`native_views/`)
  - `navigation`: navigation state, container, navigators, hooks, and linking (`navigation/`)
  - `net`: awaitable HTTP client (`net.py`)
  - `package`: `src/pythonnative/__init__.py` exports and package boundary
  - `platform`: `Platform.OS`/`Platform.select` and version detection (`platform.py`)
  - `platform_metrics`: platform-reported metrics like safe-area insets and bar heights (`platform_metrics.py`)
  - `project`: `pythonnative.toml` config, template configurators, plugin staging, and the builder (`project/`)
  - `reconciler`: virtual view tree diffing, boundaries, and the layout pass (`reconciler/`)
  - `runtime`: framework-wide asyncio loop and thread-safe future helpers (`runtime.py`)
  - `sdk`: public extension SDK for custom native components (`sdk/`)
  - `storage`: AsyncStorage key/value persistence and `use_persisted_state` (`storage.py`)
  - `scheduler`: render batching and transition queues (`scheduler.py`)
  - `style`: StyleSheet and theming (`style.py`)
  - `testing`: public test utilities (`testing/`)
  - `utils`: shared utilities (`utils.py`)

- Other scopes:
  - `deps`: dependency updates and version pins
  - `examples`: example apps under `examples/`
  - `mkdocs`: documentation site (MkDocs/Material) configuration and content under `docs/`
  - `pyproject`: `pyproject.toml` packaging/build metadata
  - `repo`: repository metadata and top‑level files (`README.md`, `CONTRIBUTING.md`, `.gitignore`, licenses)
  - `scripts`: developer scripts under `scripts/` (e.g., `check.sh`)
  - `templates`: Android/iOS project templates under `src/pythonnative/templates/`
  - `kit`: the Swift rendering core (`templates/ios_template/PythonNativeKit/`)
  - `runtime-android`: the Kotlin rendering core (`templates/android_template/pythonnative/`)
  - `tests`: unit/integration/E2E tests under `tests/`
  - `workflows`: CI pipelines under `.github/workflows/`

Note: Avoid redundant type==scope pairs (e.g., `docs(docs)`). Prefer a module scope (e.g., `docs(core)`) or `docs(repo)` for top‑level updates.

Examples:

```text
build(deps): refresh pinned versions
chore(repo): add contributing guidelines
ci(workflows): add publish job
docs(reconciler): clarify diffing algorithm
feat(components): add Slider element
fix(cli): handle missing Android SDK gracefully
perf(reconciler): reduce allocations in list diffing
refactor(utils): extract path helpers
test: cover iOS template copy flow
```

Examples (no scope):

```text
build: update packaging metadata
chore: update .gitignore patterns
docs: add project overview
```

Breaking changes:

- Use `!` after the type/scope or a `BREAKING CHANGE:` footer.

```text
feat(hosts)!: rename create_page to create_screen

BREAKING CHANGE: API renamed; update app code and templates.
```

### Multiple scopes (optional)

- Comma‑separate scopes without spaces: `type(scope1,scope2): ...`
- Prefer a single scope when possible; use multiple only when the change genuinely spans tightly related areas.

Scope ordering (house style):

- Put the most impacted scope first (e.g., `repo`), then any secondary scopes.
- For extra consistency, alphabetize the remaining scopes after the primary.
- Keep it to 1–3 scopes max.

Example:

```text
feat(templates,cli): add ios template and wire pn init
```

## Pull requests and squash merges

- PR title: use Conventional Commit format.
  - Example: `feat(cli): add init subcommand`
  - Imperative mood; no trailing period; ≤ 72 chars; `!` for breaking changes.
- PR description: include brief sections: What, Why, How (brief), Testing, Risks/Impact, Docs/Follow‑ups.
  - Link issues with keywords (e.g., `Closes #123`).
- Merging: prefer "Squash and merge" with "Pull request title and description".
- Keep PRs focused; avoid unrelated changes in the same PR.

Recommended PR template:

```text
What
- Short summary of the change

Why
- Motivation/user value

How (brief)
- Key implementation notes or decisions

Testing
- Local/CI coverage; links to tests if relevant

Risks/Impact
- Compat, rollout, perf, security; mitigations

Docs/Follow-ups
- Docs updated or TODO next steps

Closes #123
BREAKING CHANGE: <details if any>
Co-authored-by: Name <email>
```

## Pull request checklist

- PR title: Conventional Commits format (CI-enforced by `pr-lint.yml`).
- Tests: added/updated; `uv run pytest` passes.
- Lint/format: `uv run ruff check .` and `uv run black --check src examples tests` pass.
- Docs: update `README.md` if behavior changes.
- Templates: update `src/pythonnative/templates/` if generator output changes.
- No generated artifacts committed.

## Versioning and releases

- The version is tracked in `pyproject.toml` (`project.version`) and mirrored in `src/pythonnative/__init__.py` as `__version__`. Both files are updated automatically by [python-semantic-release](https://python-semantic-release.readthedocs.io/).
- **Automated release pipeline** (on every merge to `main`):
  1. `python-semantic-release` scans Conventional Commit messages since the last tag.
  2. It determines the next SemVer bump: `feat` → **minor**, `fix`/`perf` → **patch**, `BREAKING CHANGE` → **major** (minor while version < 1.0).
  3. Version files are updated, `CHANGELOG.md` is generated, and a tagged release commit (`chore(release): vX.Y.Z`) is pushed.
  4. A GitHub Release is created with auto-generated release notes and the built sdist/wheel attached.
  5. When drafts are disabled, the package is also published to PyPI via Trusted Publishing.
- **Draft / published toggle**: the `DRAFT_RELEASE` variable at the top of `.github/workflows/release.yml` controls release mode. Set to `"true"` (the default) for draft GitHub Releases with PyPI publishing skipped; flip to `"false"` to publish releases and upload to PyPI immediately.
- Commit types that trigger a release: `feat` (minor), `fix` and `perf` (patch), `BREAKING CHANGE` (major). All other types (`build`, `chore`, `ci`, `docs`, `refactor`, `revert`, `style`, `test`) are recorded in the changelog but do **not** trigger a release on their own.
- Tag format: `v`-prefixed (e.g., `v0.4.0`).
- Manual version bumps are no longer needed: just merge PRs with valid Conventional Commit titles. For ad-hoc runs, use the workflow's **Run workflow** button (`workflow_dispatch`).

### Branch naming (suggested)

- Use lowercase kebab‑case; concise (≤ 40 chars).
- Branch prefixes match Conventional Commit types:
  - `feat/<scope>-<short-desc>`
  - `fix/<issue-or-bug>-<short-desc>`
  - `chore/<short-desc>`
  - `docs/<short-desc>`
  - `ci/<short-desc>`
  - `refactor/<scope>-<short-desc>`
  - `test/<short-desc>`
  - `perf/<short-desc>`
  - `build/<short-desc>`

Examples:

```text
feat/cli-init
fix/core-threading-deadlock-123
docs/contributing
ci/publish-pypi
build/lock-versions
refactor/utils-paths
test/templates-android
fix/cli-regression
```

### E2E tests (Maestro)

End-to-end tests use [Maestro](https://maestro.dev/) to drive the dedicated `examples/e2e-suite` app on real emulators and simulators. That app contains one screen per public symbol in `pythonnative.__all__`; every flow under `tests/e2e/flows/<category>/` exercises one symbol.

The dedicated `examples/hello-world` app is left in place as a small marketing demo; it's **not** the E2E target.

```bash
# Install Maestro (one-time)
curl -Ls "https://get.maestro.mobile.dev" | bash

# For iOS, also install idb-companion
brew tap facebook/fb && brew install idb-companion
```

Build and run everything via the convenience script:

```bash
# Android (emulator must be running)
uv run ./scripts/run-e2e.sh android

# iOS (simulator must be running)
uv run ./scripts/run-e2e.sh ios
```

For tight iteration, run a single category instead of the full pass:

```bash
uv run ./scripts/run-e2e.sh android hooks
uv run ./scripts/run-e2e.sh ios components
```

Available categories: `components`, `hooks`, `navigation`, `layout`, `styling`, `animations`, `misc`.

A coverage checker, `scripts/check-e2e-coverage.py`, gates CI: every name in `pythonnative.__all__` must be covered by a demo + flow, or listed in `INTENTIONAL_EXEMPTIONS` with a justification.

When you add a new public symbol you must also:

1. Add a demo screen under `examples/e2e-suite/app/screens/<category>/`.
2. Append a `DemoEntry` in `examples/e2e-suite/app/registry.py`.
3. Add a Maestro flow at `tests/e2e/flows/<category>/<name>.yaml`.
4. Append the flow to the top-level `tests/e2e/android.yaml`, `tests/e2e/ios.yaml`, and the matching `tests/e2e/suites/<category>.yaml`.
5. Confirm `uv run python scripts/check-e2e-coverage.py` exits 0.

`tests/e2e/AGENTS.md` is the deeper reference (label conventions, failure triage, naming rules); AI agents should read it before touching the suite. The `e2e.yml` workflow runs the suite automatically on pushes to `main` and PRs.

### CI

- **CI** (`ci.yml`): runs formatter, linter, type checker, and tests on every push and PR.
- **E2E** (`e2e.yml`): builds the hello-world example on Android (Linux emulator) and iOS (macOS simulator), then runs Maestro flows. Triggers on pushes to `main`, PRs, and manual dispatch.
- **Packages** (`packages.yml`): resolves the PyPI compatibility matrix in `tests/packages/matrix.toml` against the live indexes with `scripts/package-matrix.py --check`, weekly and on changes to the resolver or manifest, and uploads the rendered Markdown table for `docs/guides/pypi-packages.md`.
- **PR Lint** (`pr-lint.yml`): validates the PR title against Conventional Commits format (protects squash merges) and checks individual commit messages via commitlint (protects rebase merges). Recommended: add the **PR title** job as a required status check in branch-protection settings.
- **Release** (`release.yml`): runs on merge to `main`; computes version, generates changelog, tags, creates GitHub Release, and (when `DRAFT_RELEASE` is `"false"`) publishes to PyPI.
- **Docs** (`docs.yml`): builds the MkDocs site in strict mode on every push and pull request, and deploys to GitHub Pages on push to `main`.

## Security and provenance

- Avoid bundling secrets or credentials in templates or code.
- Prefer runtime configuration via environment variables in CI.

## License

By contributing, you agree that your contributions are licensed under the repository's MIT License.
