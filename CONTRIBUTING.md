### Contributing to PythonNative

Thanks for your interest in contributing. This repository contains the PythonNative library, CLI, templates, a demo app, and a Django site used for docs/demo hosting and E2E. Contributions should keep the code reliable, cross‑platform, and easy to use.

## Quick start

Development uses Python ≥ 3.10.

```bash
# one-shot: creates .venv, syncs CI deps, runs every CI check
# (requires uv: https://docs.astral.sh/uv/getting-started/installation/)
./scripts/check.sh

# Run individual steps if you only want one
pytest -q
ruff check .
black src examples tests
```

Common library and CLI entry points:

```bash
# CLI help
pn --help

# create a new sample app (template fetch is remote)
pn init my_app

# run the Hello World example
cd examples/hello-world && pn run android
```

## Project layout (high‑level)

- `src/pythonnative/` – installable library and CLI
  - `pythonnative/` – core cross‑platform UI components and utilities
  - `cli/` – `pn` command
- `tests/` – unit tests for the library
- `templates/` – Android/iOS project templates and zips
- `examples/` – runnable example apps
  - `hello-world/` – minimal demo app using the library
- `README.md`, `pyproject.toml` – repo docs and packaging

## Coding guidelines

- Style: Black; lint: Ruff; typing where useful. Keep APIs stable.
- Prefer explicit, descriptive names; keep platform abstractions clean.
- Add/extend tests under `tests/` for new behavior.
- Do not commit generated artifacts or large binaries; templates live under `templates/`.
- Docstrings: Google style throughout. Ruff is configured with the Google
  convention (`pydocstyle.convention = "google"`) and enforces the `D` rule
  set on `src/pythonnative/`. See the
  [Documentation style guide](https://docs.pythonnative.com/meta/style-guide/)
  for examples and Markdown/grammar conventions.

Common commands:

```bash
./scripts/check.sh            # run all CI checks (mirrors ci.yml)
pytest -q                     # run tests
ruff check .                  # lint
black src examples tests      # format
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

- `build` – build system or external dependencies (e.g., requirements, packaging)
- `chore` – maintenance (no library behavior change)
- `ci` – continuous integration configuration (workflows, pipelines)
- `docs` – documentation only
- `feat` – user‑facing feature or capability
- `fix` – bug fix
- `perf` – performance improvements
- `refactor` – code change that neither fixes a bug nor adds a feature
- `revert` – revert of a previous commit
- `style` – formatting/whitespace (no code behavior)
- `test` – add/adjust tests only

Recommended scopes (choose the smallest, most accurate unit; prefer module/directory names):

- Module/directory scopes:
  - `alerts` – imperative Alert/Picker helpers (`alerts.py`)
  - `animated` – Animated namespace and animation primitives (`animated.py`)
  - `cli` – CLI tool and `pn` command (`src/pythonnative/cli/`)
  - `components` – declarative element-creating functions (`components.py`)
  - `element` – Element descriptor class (`element.py`)
  - `hooks` – function components and hooks (`hooks.py`)
  - `hot_reload` – file watcher and module reloader (`hot_reload.py`)
  - `layout` – pure-Python flexbox engine (`layout.py`)
  - `native_modules` – native API modules for device capabilities (`native_modules/`)
  - `native_views` – platform-specific native view creation and updates (`native_views/`)
  - `navigation` – navigation containers and stack/tab/drawer navigators (`navigation.py`)
  - `package` – `src/pythonnative/__init__.py` exports and package boundary
  - `platform` – `Platform.OS`/`Platform.select` and version detection (`platform.py`)
  - `platform_metrics` – platform-reported metrics like safe-area insets and bar heights (`platform_metrics.py`)
  - `reconciler` – virtual view tree diffing and reconciliation (`reconciler.py`)
  - `screen` – screen host, native lifecycle bridge, and render scheduling (`screen.py`)
  - `sdk` – public extension SDK for custom native components (`sdk/`)
  - `style` – StyleSheet and theming (`style.py`)
  - `utils` – shared utilities (`utils.py`)

- Other scopes:
  - `deps` – dependency updates and version pins
  - `examples` – example apps under `examples/`
  - `mkdocs` – documentation site (MkDocs/Material) configuration and content under `docs/`
  - `pyproject` – `pyproject.toml` packaging/build metadata
  - `repo` – repository metadata and top‑level files (`README.md`, `CONTRIBUTING.md`, `.gitignore`, licenses)
  - `scripts` – developer scripts under `scripts/` (e.g., `check.sh`)
  - `templates` – Android/iOS project templates under `src/pythonnative/templates/`
  - `tests` – unit/integration/E2E tests under `tests/`
  - `workflows` – CI pipelines under `.github/workflows/`

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
feat(screen)!: rename create_page to create_screen

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
- Merging: prefer “Squash and merge” with “Pull request title and description”.
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
- Tests: added/updated; `pytest` passes.
- Lint/format: `ruff check .`, `black` pass.
- Docs: update `README.md` if behavior changes.
- Templates: update `templates/` if generator output changes.
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
- Manual version bumps are no longer needed — just merge PRs with valid Conventional Commit titles. For ad-hoc runs, use the workflow's **Run workflow** button (`workflow_dispatch`).

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

End-to-end tests use [Maestro](https://maestro.dev/) to drive the hello-world example on real emulators and simulators.

```bash
# Install Maestro (one-time)
curl -Ls "https://get.maestro.mobile.dev" | bash

# For iOS, also install idb-companion
brew tap facebook/fb && brew install idb-companion
```

Build and launch the app first, then run the tests:

```bash
cd examples/hello-world

# Android (emulator must be running)
pn run android
maestro test ../../tests/e2e/android.yaml

# iOS (simulator must be running; --platform ios needed when an Android emulator is also connected)
pn run ios
maestro --platform ios test ../../tests/e2e/ios.yaml
```

Test flows live in `tests/e2e/flows/` and cover the main screen rendering, counter interaction, and multi-screen navigation. The `e2e.yml` workflow runs these automatically on pushes to `main` and PRs.

### CI

- **CI** (`ci.yml`): runs formatter, linter, type checker, and tests on every push and PR.
- **E2E** (`e2e.yml`): builds the hello-world example on Android (Linux emulator) and iOS (macOS simulator), then runs Maestro flows. Triggers on pushes to `main`, PRs, and manual dispatch.
- **PR Lint** (`pr-lint.yml`): validates the PR title against Conventional Commits format (protects squash merges) and checks individual commit messages via commitlint (protects rebase merges). Recommended: add the **PR title** job as a required status check in branch-protection settings.
- **Release** (`release.yml`): runs on merge to `main`; computes version, generates changelog, tags, creates GitHub Release, and (when `DRAFT_RELEASE` is `"false"`) publishes to PyPI.
- **Docs** (`docs.yml`): builds the MkDocs site in strict mode on every push and pull request, and deploys to GitHub Pages on push to `main`.

## Security and provenance

- Avoid bundling secrets or credentials in templates or code.
- Prefer runtime configuration via environment variables for Django and CI.

## License

By contributing, you agree that your contributions are licensed under the repository’s MIT License.
