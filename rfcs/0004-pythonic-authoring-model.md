# RFC 0004: Pythonic authoring model

- Status: Implemented
- Author(s): Owen Carey, with Claude (Claude Code)
- Created: 2026-09-29
- Implemented in: (this pull request)
- Supersedes / Superseded by: replaces the navigation factories, route-name
  navigation, `LinkingConfig`, and `NavigationTheme` from RFC 0002, and the
  `Theme` and `StyleSheet` design that predates the RFC process

## Summary

The last four releases brought PythonNative's runtime close to React
Native's: native widgets, Yoga layout, revisioned commits, virtualized lists,
native animation graphs, and a broad device API. The code an application
developer writes hasn't kept up. It's React transcribed into Python: screens
are strings, navigators are stateless factories, styles are anonymous dicts,
global state is hand-rolled, and the type annotations that promise editor
checking fail under a strict type checker.

This RFC fixes the authoring model before 1.0, while breaking changes are
still cheap. Every element tree becomes honestly typed. Screens become
ordinary components whose parameters are their route params, navigators
become module-level values, and navigation is checked by the type checker.
One `Theme` drives both application and navigation chrome, and style
sheets have attribute access. A typed `Store` replaces hand-written
subscription code. Shared prop definitions replace 19 copied keyword blocks.
The reconciler skips unchanged subtrees. A `pn lint` command enforces the
rules of hooks. It also fixes correctness bugs found while auditing these
areas and closes two development-server exposures.

## Motivation

A September 2026 audit (v0.47.0) compared a representative application,
the examples, and the public signatures with idiomatic React Native and
idiomatic Python.

### The types don't hold

`mypy.ini` sets `strict_optional = False`, excludes `examples/inbox` and
`examples/e2e-suite`, and disables `attr-defined` for `pythonnative.*`.
With those switches off, the documented patterns look typed. Turned on:

- Children are declared `*children: Element`, but conditional children are
  the documented idiom. `pn.Column(pn.Text(status) if status else None)`,
  which the Inbox example writes, is a type error.
- `key=` is accepted at every component call site at runtime, but
  `Card(title="x", key=item.id)` is a type error. PEP 612 doesn't allow a
  keyword parameter between `*args: P.args` and `**kwargs: P.kwargs`, and
  both mypy and pyright reject the attempt. The workaround,
  `Card.keyed(item.id)(title="x")`, is a curried call nobody would guess.
- `StyleSheet.create(...)` returns `Dict[str, Style]`, so `styles["titel"]`
  passes the type checker and fails at runtime.
- Route params are a `dict[str, Any]`. `use_route(DetailParams)` checks a
  `TypedDict` at runtime, but nothing checks `nav.navigate("Detail", idd=4)`.

### Navigation is stringly typed and React-shaped

```python
Stack = pn.create_stack_navigator()        # a class of static methods, no state

@pn.component
def DetailScreen():
    route = pn.use_route(DetailParams)     # params arrive through a hook
    return pn.Text(f"Item {route.params['id']}")

Stack.Navigator(
    Stack.Screen("Home", HomeScreen, options={"title": "Home"}),   # two option styles
    Stack.Screen("Detail", DetailScreen, title="Detail"),
)
nav.navigate("Detail", id=42)              # unchecked string and params
```

Deep links repeat every route name in a separate `LinkingConfig` tree,
and a navigation theme duplicates colors the application theme already
defines. Screen options come from three places (keywords, an `options=`
dict, and an `options=` callable), and `header_left` accepts either an
element or a factory.

### Styles and themes don't scale

- `Theme` is a closed dataclass of nine colors and fixed sizes, with no way to
  add a token.
- `NavigationTheme` is a second, incompatible theme.
- Neither example calls `use_theme`, so neither supports dark mode. The
  Inbox example shadows `pn.ThemeContext` with its own
  `create_context("#FFFFFF")`.
- The examples contain 275 `pn.style(...)` calls and 42 inline style dicts
  with hard-coded colors.
- `spacing` and `gap` are two names for one Yoga property.

### State management is left to the application

The FAQ tells developers to hand-roll a store. The Inbox example does: a
listener set, a `publish` method, a frozen snapshot, a context, and
`use_subscription(repository.subscribe, lambda: repository.snapshot)`.
That last line has a bug the framework causes: `equality.equal` treats
every callable as changed unless it's the identical object, and
`repository.subscribe is repository.subscribe` is `False` for a bound
method. The subscription is torn down and recreated on every render. The
same rule defeats `memo` whenever a bound method is passed as a prop.

`use_persisted_state` writes storage from inside a state updater (which
transitions may replay), loses a value set before its first load finishes,
and types its setter as `Callable[[Any], None]`.

### Repetition and avoidable work

- **Copied props:** every container factory copies the same 16
  accessibility and layout keyword parameters, 19 copies in all.
- **Validation cost:** built-in element factories validate props and styles
  on every construction, even in release builds. That's about 40% of
  element-construction cost.
- **No identity check:** the reconciler never tests whether a child element
  is the identical object it rendered last time, so passing `*children`
  through a component always re-renders them.
- **Context propagation:** a provider value change walks the provider's
  entire subtree looking for consumers.

### Tooling gaps and exposures

- **No hook linter:** Python has no equivalent of
  `eslint-plugin-react-hooks`, so a hook inside an `if` or a stale closure
  in an effect is found only at runtime, if at all.
- **Fast Refresh remounts too often:** it remounts the whole application
  whenever a changed module defines a public class or plain function. The
  `pn init` scaffold's own `class DetailParams(TypedDict)` triggers this,
  so every save of a new project's `main.py` resets its state.
- **The dev server is open:** it binds `0.0.0.0` without authentication or
  a WebSocket `Origin` check. Any device on the network, and any web page
  the developer visits, can read the full application source through
  `/file/` or `/ws`.
- **Release builds carry dev code:** they ship `cli/`, `project/`,
  `devserver/`, and `testing/`, and iOS release builds keep the
  local-network usage description.

## Reference behavior

React and React Native define the semantics this RFC keeps: function
components, hooks, keyed reconciliation, context, and a navigation model
with stacks, tabs, and drawers. Where the idiom is JavaScript-specific,
PythonNative now follows the Python idiom instead:

| Concern | React Native | PythonNative after this RFC |
| --- | --- | --- |
| Element keys | `key` prop | `key=` on built-ins; `.with_key()` on any element, because PEP 612 can't type `key=` on a user component |
| Screens and params | `navigation.navigate("Detail", {id})`, typed through a `ParamList` | `nav.push(DetailScreen(id=42))`; params are the component's parameters, so the type checker verifies them |
| Navigator definition | `createNativeStackNavigator()`, or the static config API | `Root = pn.StackNavigator(Home, pn.Screen(Detail, title="Detail"))`, a module-level value |
| Deep links | A `linking.config` tree parallel to the navigators | `pn.Screen(Detail, path="items/{id}")`, with params converted from the component's annotations |
| Themes | Separate app and navigation themes | One `Theme` dataclass; subclass it to add tokens |
| Style sheets | `StyleSheet.create({...})` | A class namespace: `class Styles(pn.StyleSheet): card = pn.style(...)` |
| Global state | Zustand, Redux, or Jotai | `pn.Store[T]` with `pn.use_store(store, selector)` |
| Rules of hooks | `eslint-plugin-react-hooks` | `pn lint` |

React Navigation 7's static configuration API is the closest precedent for
module-level navigators. It exists for the same reasons: type inference and
deep links that don't repeat the route tree.

## Design

### Typed element trees

`pythonnative.Node` becomes the recursive alias for anything that can
appear in a tree:

```python
type Node = Element | None | bool | Iterable[Node]
```

Every built-in container declares `*children: Node`, and component bodies
return `Node`. `None`, `False`, and nested iterables are dropped during
reconciliation as they are today, so the annotation now describes behavior
that already exists. Strings aren't nodes; text needs `pn.Text`.

Keys:

- Built-in factories keep their typed `key: str | None` parameter.
- Every element has `with_key(key) -> Element`, the typed way to key a user
  component: `Row(item).with_key(item.id)`.
- `Component.__call__` raises `TypeError` for `key=`, with a message
  pointing to `.with_key()`, instead of silently consuming it.
- `@component` rejects a function that declares a parameter named `key`,
  since the name is reserved for element identity.
- `Component.keyed` is removed.

### Screens are components; navigators are values

```python
import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()
    return pn.Button("Open 42", on_press=lambda: nav.push(ItemScreen(id=42)))


@pn.component
def ItemScreen(id: int, tab: str = "details") -> pn.Node:
    pn.use_screen_options(title=f"Item {id}")
    return pn.Text(f"Item {id} ({tab})")


Tabs = pn.TabNavigator(
    pn.Screen(FeedScreen, title="Feed", tab_bar_icon="house", path="feed"),
    pn.Screen(ProfileScreen, title="Me", tab_bar_icon="user", path="me/{user}"),
    name="Main",
)

Root = pn.StackNavigator(
    pn.Screen(Tabs, header_shown=False),
    pn.Screen(ItemScreen, path="items/{id}"),
    pn.Group(pn.Screen(ComposeScreen), presentation="modal"),
    screen_options=pn.ScreenOptions(header_large_title=True),
)


@pn.component
def App() -> pn.Node:
    return pn.NavigationContainer(Root, link_prefixes=["myapp://"])
```

Python API (`pythonnative.navigation`, re-exported from `pythonnative`):

- `StackNavigator(*screens, name=None, initial=None, screen_options=None)`,
  `TabNavigator(..., tab_bar_style=None)`, and
  `DrawerNavigator(..., drawer_width=280)` build immutable `Navigator`
  values.
  - Calling a navigator (`Root()`) returns its element, so a navigator is
    a zero-argument component and can itself be a screen.
- `Screen(component, *, name=None, path=None, **options: Unpack[ScreenOptions])`.
  A bare component or navigator in a navigator's list is shorthand for
  `Screen(component)`.
  - The route name defaults to the component's `display_name` or the
    navigator's `name`. Duplicate names within a navigator raise
    `ValueError`, suggesting `name=`.
  - A navigator's initial screen gets its params from `initial`; every
    other tab and drawer screen must be callable without arguments,
    because keep-alive navigators create all their routes up front. Both
    are checked when the navigator is built.
- `Group(*screens, **options: Unpack[ScreenOptions])` layers options over its
  screens.
- `initial` is a component, a navigator, or an element carrying params
  (`initial=ItemScreen(id=1)`).
- `NavigationContainer(navigator, *, ref=None, link_prefixes=(), initial_state=None, on_state_change=None, on_ready=None)`.
- `NavigationRef()` is constructed directly and mirrors the handle's
  actions from the root navigator.

Params and targets:

- A route's params are the props the caller passed to the screen's
  element; parameter defaults the call filled in aren't stored, so
  navigating back to an existing route merges only what was passed.
  `nav.push(ItemScreen(id=42))` builds an element through the component's
  own signature, so a missing or mistyped param is a static error and,
  failing that, a `TypeError` at the call.
- The screen renders as `ItemScreen(**route.params)`. `initial_params` is
  gone: parameter defaults serve that purpose.
- `use_route()` returns the untyped `Route` (name, key, params) for code
  that needs identity. `use_route(ParamsType)` and the generic `Route[P]`
  are removed.

The `Navigation` handle:

- `navigate(target)`, `push(target)`, and `replace(target)` take an
  element.
- `pop_to(target)` and `jump_to(target)` accept a component or navigator
  (no params) or an element (params merged).
- `reset(*targets, index=None)` and `set_params(**params)` update state.
  `set_params` re-renders the screen with new props.
- `set_options(**options: Unpack[ScreenOptions])` sets options
  imperatively.
- `pop`, `go_back`, `pop_to_top`, `can_go_back`, `is_focused`,
  `get_parent`, `get_state`, `add_listener`, and the drawer methods keep
  their behavior.
- `pn.use_screen_options(**options: Unpack[ScreenOptions])` sets the
  calling screen's options from its render.
  - It's a layout effect that calls `set_options` only when the options
    differ.
  - Navigators cache each route's body element by identity, so the
    navigator re-render it causes doesn't re-render the screen.

Target resolution:

- A target is found by component identity, falling back to module and
  qualified name after a Fast Refresh swap.
- Search order is the current navigator, then navigators statically nested
  in it, then each ancestor in turn. Navigating to a screen inside a nested
  navigator seeds the nested state automatically, so
  `nav.navigate(ProfileScreen(user="ada"))` works from any screen. No
  `screen=` argument is needed.

Options:

- There's exactly one way to set static options: keywords on `Screen`,
  `Group`, or `screen_options=`.
- There's exactly one way to set dynamic options: `use_screen_options` or
  `set_options`.
- The `options=` dict, the `(route) -> options` callables, and
  factory-valued header slots are removed. `header_left` and
  `header_right` take an element.

Deep links:

- `path` uses Python format-string placeholders (`"items/{id}"`).
- A nested navigator's path prefixes its screens' paths.
- Path and query values convert through the screen component's parameter
  annotations: `str`, `int`, `float`, `bool`, `Enum` subclasses,
  `Literal` values, and `Optional[...]` of those. A failed conversion or a
  missing required parameter rejects the URL instead of passing a string
  through, and query parameters the component doesn't accept are ignored.
- The container builds the pattern table by walking the static navigator
  tree once, so there's no parallel route tree to maintain.

Wire contract: unchanged. Native `Screen`, `ScreenStack`, and `TabBar`
props and the serialized navigation state (`routes`, `index`, `name`,
`params`, `key`) keep their shape. Route names still travel as strings.
Params must remain JSON-serializable for native state caching, as before.

### One theme, typed style sheets

```python
@dataclass(frozen=True, kw_only=True)
class BrandTheme(pn.Theme):
    accent: pn.Color = "#FF2D55"


class Styles(pn.StyleSheet):
    row = pn.style(padding=16, gap=6, border_bottom_width=1)
    title = pn.style(font_size=17, font_weight="600")


class CardStyles:
    def __init__(self, theme: BrandTheme) -> None:
        self.card = pn.style(background_color=theme.colors.surface, border_radius=theme.radii.md)
        self.badge = pn.style(background_color=theme.accent)


@pn.component
def Card(title: str) -> pn.Node:
    styles = pn.use_styles(CardStyles)          # built once per theme
    theme = pn.use_theme(BrandTheme)            # typed as BrandTheme
    return pn.View(pn.Text(title, style=[Styles.title, {"color": theme.colors.text}]), style=styles.card)
```

- `Theme` is a frozen, keyword-only dataclass:
  - `dark: bool`.
  - `colors: Colors`, with `primary`, `background`, `surface`, `text`,
    `text_secondary`, `border`, `error`, `success`, and `warning`.
  - `typography: Typography`, with `title`, `heading`, `body`, `label`,
    and `caption`, each a `Style`.
  - `spacing: Spacing`, with `xs`, `sm`, `md`, `lg`, and `xl`.
  - `radii: Radii`, with `sm`, `md`, `lg`, and `full`.
  - Applications add tokens by subclassing.
- `LIGHT_THEME` and `DARK_THEME` are the built-in presets.
- `ThemeProvider(*children, light=LIGHT_THEME, dark=DARK_THEME)` selects by
  the effective color scheme. Passing the same theme twice pins it.
- `use_theme()` returns `Theme`. `use_theme(BrandTheme)` returns
  `BrandTheme` and raises `TypeError` if the provided theme isn't one.
- Navigators draw their chrome from the theme:
  - `colors.primary`: tint.
  - `colors.surface`: header and tab bar.
  - `colors.background`: screens.
  - `colors.text` and `colors.border`: title text and hairlines.
  - `colors.error`: badges.
- `StyleSheet` is a namespace base class. Subclass attributes are `Style`
  dicts, validated once in dev mode. Instantiating one raises `TypeError`.
  Attribute access makes a misspelled style a static error.
- `use_styles(factory)` calls `factory(theme)` once per theme identity and
  returns the result with its own type. Any `Callable[[T], S]` works: a
  class with an `__init__(theme)`, or a function.
- `ABSOLUTE_FILL` replaces `StyleSheet.absolute_fill()`. Composition is a
  style list (`style=[a, b]`).

Wire contract: the `spacing` style key is removed from `Style`, the layout
engines (Swift, Kotlin, the browser's `layout.js`, and the Python layout
mirror), and the generated contracts. `gap` is the only name. The contract
fingerprint changes, so extension contracts and dev clients must be
regenerated. `PROTOCOL_VERSION` is unchanged because no message shape
changes.

### Stores and hook correctness

```python
@dataclass(frozen=True)
class Inbox:
    issues: tuple[Issue, ...] = ()
    query: str = ""


store = pn.Store(Inbox())


def set_query(text: str) -> None:
    store.update(lambda state: replace(state, query=text))


@pn.component
def Count() -> pn.Node:
    count = pn.use_store(store, lambda state: len(state.issues))  # re-renders only when the count changes
    return pn.Text(f"{count} issues")
```

- `Store[T]`:
  - `get() -> T`.
  - `set(value: T)` and `update(fn: Callable[[T], T])`.
  - `subscribe(listener) -> unsubscribe`.
  - `batch()`, a context manager that coalesces notifications.
  - Writes apply immediately under a lock, so `get()` is current on every
    thread. Listeners run on the writing thread; `use_store` (through
    `use_subscription`) compares and schedules its re-render on the
    application thread.
- `use_store(store) -> T` and `use_store(store, selector: Callable[[T], S]) -> S`.
  The component re-renders only when the selected value changes under the
  framework's equality rule. The selector may be a fresh lambda each render.
- `equality.equal` compares bound methods by their `__self__` and
  `__func__`, fixing `use_subscription` resubscription and `memo` misses.
- `use_persisted_state(key, initial: T) -> tuple[T, StateSetter[T]]`:
  - Writes storage from an effect after a committed change, never from an
    updater.
  - A value set before loading finishes wins over the stored value and is
    persisted.
- `TransitionQueue.flush` runs every queued trigger even when one raises,
  then re-raises the first error.

### Shared, typed props

`pythonnative.components.props` defines `AccessibilityProps`, a `TypedDict`
of the eleven accessibility keys plus `test_id`, and `ViewProps`, which adds
`gestures`, `hit_slop`, and `on_layout`.

- Containers declare
  `def Column(*children: Node, style: StyleProp = None, ref=None, key=None, **props: Unpack[ViewProps])`.
- `_make_element` normalizes `accessibility_value` and
  `accessibility_actions` once.
- The generated API reference documents the two `TypedDict`s once instead
  of in every factory.

Validation moves to development:

- Built-in prop validation (`sdk.builtins.validate_props`) and style-key
  validation run only when `diagnostics.is_dev()` is true.
- In dev mode, a user component's props are checked against its
  annotations, and a mismatch produces one `diagnostics` warning per
  component and parameter.
  - The checker understands `str`, `int`, `float` (accepting `int`),
    `bool`, `None`, `Optional`, `Union`, `Literal`, `Sequence`, `Mapping`,
    `Callable`, dataclasses, and plain classes.
  - It skips annotations it can't evaluate.
  - Static checking remains the primary guard.

### Reconciler work

- **Identity bailout:** when a child element is the identical object the node
  last rendered and the node has no pending work, reconciliation reuses the
  node and its subtree.
  - Dirty descendants are still in the dirty queue and render in their own
    pass.
  - Context consumers are marked through the registry below.
  - Navigators and passed-through `*children` benefit without any API
    change.
- **Consumer registry:** `use_context` records the providing node, and each
  provider keeps a set of consumer nodes that is updated on render and
  unmount. A changed provider value marks exactly those consumers, instead
  of walking its subtree.
- **Surfaced errors:** exceptions from a custom `memo(equal=...)` comparator
  are reported through `diagnostics` in dev mode instead of being swallowed.

### Tooling

- **`pn lint [paths...]` (`--json`):**
  - AST-based and dependency-free. It exits nonzero on findings and runs
    in CI over `src`, `examples`, and the templates.
  - Rules:
    - `PN101`: a hook call inside a conditional, loop, comprehension,
      `try`, or nested function, or after an early `return`.
    - `PN102`: a hook called outside a `@component` function or a `use_*`
      custom hook.
    - `PN103`: a local name read by a `use_effect`, `use_layout_effect`,
      `use_memo`, or `use_callback` callback is missing from a literal
      deps list. Names defined at module level, setters returned by
      `use_state` and `use_reducer`, and refs from `use_ref` are exempt,
      as in React.
    - `PN104`: `key=` passed to a call of a module-level `@component`.
  - Findings can be suppressed with `# pn: ignore[PN103]`.
- **Fast Refresh** remounts only when a changed module redefines a class whose
  definition actually changed. Class fingerprints hash field names, bases,
  and method code objects. Functions, `TypedDict`s, `Protocol`s, and
  unchanged classes (`Enum`s included) no longer force a remount.
- **The `pn init` scaffold** uses typed screens, a module-level
  `StackNavigator`, and theme-derived styles through `use_styles`, and
  passes `pn lint` and strict mypy (a test enforces both).
- **Typing conformance:** `tests/typing/` holds files that mypy checks with
  `warn_unused_ignores`. Every expected error carries a
  `# type: ignore[code]`, so an API that stops rejecting a mistake fails CI
  as surely as one that starts rejecting correct code.
- **mypy configuration:**
  - `strict_optional` is on.
  - `examples/inbox` and `examples/e2e-suite` are checked with
    `mypy --strict` from their own directories, because each owns a
    top-level `app` package that whole-tree mode can't resolve twice.
  - The blanket `attr-defined` and `no-redef` suppressions are removed.

### Development server and release hygiene

- `pn start` generates a random per-user token, stored with mode `0600` in
  `~/.pythonnative/dev-token` and reused across restarts so installed debug
  builds keep connecting.
  - `PN_DEV_TOKEN` supplies the token directly and `PN_DEV_TOKEN_FILE`
    moves the file; deleting the file issues a new token.
  - `pn run` bakes it into `PN_DEV_SERVER` as a `token` query parameter.
  - The printed preview URL carries it once, and the page exchanges it for
    an `HttpOnly`, `SameSite=Strict` cookie through a redirect to `/`.
  - `/file/`, `/manifest`, `/status`, `/assets/`, and `/ws` require the
    token as the `token` query parameter, an `X-PN-Token` header, or the
    cookie (`401` without one, `403` for a wrong one); `index.html` and
    the static renderer files, including the generated `schema.js`,
    don't. Responses drop `Access-Control-Allow-Origin: *`.
  - The `--dev-client` connect screen accepts the printed device URL,
    token included.
- WebSocket upgrades from a browser must carry an `Origin` whose host
  matches the request's `Host`. Native dev clients send no `Origin`.
  Refused upgrades get a plain HTTP error before any upgrade.
- Release bundles exclude dev-only modules:
  - `pythonnative/cli`, `project`, `devserver`, and `testing`.
  - `devclient.py`, `hot_reload.py`, `refresh.py`, and the browser
    preview (`preview.py` and `bridge/web.py`).
  - The SDK code generators (`sdk/codegen.py`, `contract_codegen.py`,
    `module_codegen.py`, and `sdk/templates`).
  - Runtime code stops importing them: `overlay_root` moves to
    `pythonnative.utils`, the Fast Refresh fingerprint in `component.py`
    becomes an optional lazy import, and `pythonnative.sdk` stops
    re-exporting `generate`.
  - Import checks in `tests/test_release_packaging.py` keep the runtime
    free of imports from those modules; function-local imports on
    development-only paths are allowlisted explicitly.
- iOS release builds omit `NSLocalNetworkUsageDescription`.

## Removals

- `create_stack_navigator`, `create_tab_navigator`, `create_drawer_navigator`,
  the `StackNavigator`/`TabNavigator`/`DrawerNavigator` factory classes and
  their `Screen`/`Group`/`Navigator` static methods, `ScreenDef`, and
  `ScreenGroup`. The names `StackNavigator`, `TabNavigator`, and
  `DrawerNavigator` now denote navigator values.
- Route-name navigation (`navigate("Detail", id=1)`), the `screen=` nested
  target argument, `initial_route`, `initial_params`, the `options=`
  argument, `(route) -> options` callables, and factory-valued header slots.
- `LinkingConfig` and its `screens` tree (replaced by screen `path`s and
  `pythonnative.navigation.LinkTable`); `use_route(ParamsType)` and the
  generic `Route[P]`/`RouteParams`; `create_navigation_ref`.
- `NavigationTheme`, `NavigationColors`, `DEFAULT_NAVIGATION_THEME`,
  `DARK_NAVIGATION_THEME`, `use_navigation_theme`, and
  `NavigationContainer(theme=...)`.
- The flat `Theme` fields (`primary_color`, `font_size_title`, ...),
  `Theme.replace`, `DEFAULT_LIGHT_THEME`, `DEFAULT_DARK_THEME`,
  `default_theme`, and `ThemeContext` as public API (use `ThemeProvider`).
- `StyleSheet.create`, `StyleSheet.compose`, `StyleSheet.flatten`, and
  `StyleSheet.absolute_fill`.
- The `spacing` style key.
- `Component.keyed`, runtime consumption of `key=` by user components, and
  components declaring a `key` parameter.
- Per-factory copies of the accessibility keyword parameters.
- Production-time built-in prop and style validation.
- The subtree walk in `_mark_context_consumers`.
- The `pythonnative.sdk.generate` re-export (import it from
  `pythonnative.sdk.codegen`) and `pythonnative.hot_reload.overlay_root`
  (now `pythonnative.utils.overlay_root`).
- `pythonnative.project.android.LIB_IGNORE` (replaced by
  `pythonnative.project.bundle`).
- Unauthenticated access to the dev server, and its
  `Access-Control-Allow-Origin: *` header.

No aliases or deprecation shims are kept. Examples, templates, tests, and
documentation move to the new API in the same change.

## Alternatives considered

- **`with` block builders** (`with pn.Column(): pn.Text("Hi")`). They read
  well for conditionals and loops, but:
  - Construction would register an element with an implicit parent
    through a context variable. Every element passed as a prop
    (`header_right=`, `fallback=`, `ListEmptyComponent`, a render callback's
    result) would then attach to the wrong parent unless it was built
    outside a block.
  - Nested calls would become a second way to build the same tree.
  - Block-built children can't be typed.

  Nested calls with honest `Node` types and short style references keep one
  construction model.
- **File-based routing** (Expo Router style). Directory conventions trade
  static typing for convention; a route file's params can't be checked at a
  `push` call. Typed module-level navigators give the static route tree
  without the magic. File-based routing can be layered on top later as a
  generator of `Navigator` values.
- **A mypy plugin for `key=`.** It would help mypy users only; pyright (and
  therefore most editors) would still reject `key=`. `.with_key()` is typed
  everywhere.
- **Signals or fine-grained reactivity.** A different rendering model that
  would change the semantics of every hook. `Store` plus selectors gives the
  targeted re-renders without leaving the component model.
- **Keeping navigation route names public and adding a typed layer.** Two
  addressing schemes would coexist forever. Names remain an internal detail
  of state serialization.
- **Resolving theme tokens natively.** Colors that resolve on the platform
  (like `DynamicColor`) would let static style sheets follow the theme
  without a re-render, but custom tokens and non-color values can't be
  resolved there. `use_styles` re-derives styles when the theme changes,
  which is rare.

## Non-goals

These are left for later RFCs:

- File-based routing.
- Style variants or utility-class syntax.
- A visual inspector.
- A debugger integration.
- Prebuilt dev-client apps.
- Over-the-air updates.
- A ruff or flake8 plugin: ruff doesn't load third-party rules, and
  `pn lint` has no dependencies.
- A persisted `Store` option: `use_persisted_state` and `AsyncStorage`
  cover persistence.
- Changing the native widgets, bridge encoding, or protocol version.

## Implementation decisions and limits

- **Screen resolution:** a target matches a screen by component identity
  anywhere in the static tree before the Fast Refresh fallback (module,
  qualified name, and display name) is tried, because components built by
  one factory share a qualified name.
- **Screen body caching:** navigators reuse each route's body element while
  its params and component are unchanged, so the identity bailout skips
  screens when only the navigator re-renders. As a result
  `freeze_on_blur` now matters only when a blurred screen's params change
  (it holds them back until the screen is focused again).
- **Unknown screen options** raise `TypeError` at `Screen`, `Group`,
  `screen_options=`, and `set_options`, in line with the typed keywords.
- **Built-in list components:** `FlatList` and `SectionList` are
  implemented as components but keep a typed `key=` parameter through an
  internal `builtin_component` marker; the key never reaches the body.
- **Children:** one-shot iterators passed as children are materialized into
  tuples, so a component that passes its `*children` through re-renders
  them on later renders.
- **`pn lint` stability rules:** besides `use_state` setters and `use_ref`,
  names bound from `use_animated_value(...)` and from `use_memo(...)` or
  `use_callback(...)` with a literal empty dependency list are treated as
  stable. `builtin_component` counts as a component decorator. The
  framework source passes `pn lint`; its few deliberate mount-once reads
  carry `# pn: ignore[PN103]` comments that state the reason.
- **Screens paint the theme's `colors.background`**, on native stacks and in
  the headless renderer.
- **Hello World** persists its appearance choice with `use_persisted_state`
  and applies it with `appearance.set_color_scheme`; **Inbox** keeps a
  module-level repository whose `Store[Snapshot]` replaces the listener
  set, context, and `use_subscription` wiring.

## Testing and rollout

- **Python tests:**
  - Rewrite the navigation, theme, style, hook, and reconciler tests for
    the new APIs.
  - Add tests for `Store`, `use_store`, identity bailout, the consumer
    registry, deep-link conversion, nested target resolution, the
    persisted-state race, bound-method equality, class-fingerprint Fast
    Refresh, `pn lint` rules, dev-token enforcement, the `Origin` check,
    and release bundle contents.
- **Typing:** the conformance files run under mypy as part of the test
  suite.
- **Generated contracts:** regenerate them after removing `spacing` and
  check for drift.
- **Examples and docs:**
  - Port Hello World, Inbox, and the e2e suite to typed screens, the
    theme, style sheets, and stores. Every example passes strict mypy and
    `pn lint`.
  - Rewrite the navigation, styling, state, and getting-started
    documentation. Build the docs strictly.
- **Devices:** run the reference apps on the local iOS simulator and Android
  emulator, and run the Maestro navigation and styling suites where the
  local toolchain allows.

## Recorded validation

- **Python:** 2,176 tests pass (14 skipped), including 132 navigation tests
  and the typing conformance files. Ruff, Black, mypy (254 files, with
  `strict_optional`), strict mypy on the Inbox and e2e apps, `pn lint` over
  the framework source and every example, the package build, the e2e
  coverage check, and `mkdocs build --strict` all pass.
- **Native unit tests:** PythonNativeKit's 106 XCTest cases pass on an
  iPhone 17 Pro simulator (iOS 26.2), and the Android module's JUnit and
  Robolectric tests pass, both against the regenerated contracts. The
  browser renderer acceptance tests pass in Chrome with Yoga WebAssembly.
- **iOS simulator:** a fresh `pn init` app builds, launches, and passes a
  Maestro flow that pushes a typed screen with a param and returns with
  its state intact. The e2e suite's navigation, styling, and hooks
  Maestro suites (the hooks suite includes the new `use_store` flow)
  pass on the final code.
- **Android emulator:** the styling suite passes. In the navigation suite,
  the tab navigator (including the nested native stack), drawer
  navigator, and params-passing flows pass, and a screenshot confirmed
  the transparent modal, which prompted the transparent-background fix.
  The API 31 emulator's system server crashed repeatedly on this machine
  (as recorded in RFC 0003), so a clean end-to-end Android run of the
  whole navigation suite remains unverified locally.
