# Linting

Hooks are matched to their state by call order, so a hook that runs on
one render and not the next corrupts every hook after it. A stale
dependency list is quieter: the effect keeps using the values from the
render that created it. `pn lint` catches both before you run the app.
It's the PythonNative counterpart of `eslint-plugin-react-hooks`.

The linter reads your source with Python's `ast` module. It never
imports or runs your code, and it has no dependencies beyond
PythonNative itself.

## Running it

```bash
pn lint                  # lints app/ (or the current directory if there's no app/)
pn lint app tests        # lints specific files and directories
pn lint --json           # prints a JSON array for editors and CI
```

Each finding prints as `path:line:col: CODE message`:

```text
app/main.py:14:9: PN101 hook 'use_state' is called inside an 'if' statement; call hooks unconditionally at the top level of 'Profile'
app/main.py:22:43: PN103 use_effect callback reads 'user_id' but it is missing from the dependency list
Found 2 problems.
```

`pn lint` exits 1 when it finds anything and 0 when it doesn't, so it
works as a CI gate as is. It exits 2 when a path you named doesn't
exist.

With `--json`, stdout carries only the array, one object per finding
with `path`, `line`, `col`, `code`, and `message` keys, and the summary
line goes to stderr.

Directories are searched recursively for `*.py` files. The linter skips
`.git`, `build`, `dist`, `.venv*`, `__pycache__`, `node_modules`, and
`site`. A file you name directly is linted whatever its extension.

## What counts as a hook, a component, and a custom hook

- A **hook** is any call whose final name is `use_` followed by a
  lowercase letter: `pn.use_state(...)`, `use_effect(...)`,
  `hooks.use_ref(...)`, or your own `use_cart()`. Leading underscores
  are allowed, so private helpers like `_use_navigator()` count too.
- A **component** is a function decorated with `@component`,
  `@pn.component`, or `@pythonnative.component`, including when it's
  stacked under `@pn.memo`. A function passed straight to
  `pn.component(fn)` or `Component(fn, ...)` in the same file counts
  too.
- A **custom hook** is a function whose name is a hook name, such as
  `def use_cart():`.

Components and custom hooks are the only places a hook may run.

## Rules

### PN101: hooks must run unconditionally

A hook call inside a component or custom hook must run on every render,
in the same order. `PN101` flags a hook inside any of these:

- an `if`, `elif`, or `else` block
- a `for` or `while` loop
- a `try` statement, including its `except`, `else`, and `finally`
  blocks
- a `match` statement
- a comprehension or generator expression
- a lambda
- either branch of a conditional expression (`a if cond else b`)
- the right side of `and` or `or`
- a function or class defined inside the component
- any statement after an early `return`

```python
@pn.component
def Profile(user_id: int | None) -> pn.Node:
    if user_id is None:
        return pn.Text("Signed out")
    user, set_user = pn.use_state(None)  # PN101: after an early return
    return pn.Text(f"User {user_id}")
```

Move the condition inside the hook, or call the hook first and branch
afterward:

```python
@pn.component
def Profile(user_id: int | None) -> pn.Node:
    user, set_user = pn.use_state(None)
    if user_id is None:
        return pn.Text("Signed out")
    return pn.Text(f"User {user_id}")
```

Positions that always run are fine: the test of an `if`, the iterable
of a `for` loop, a `with` statement and its body, the first operand of
`and` or `or`, and the first iterable of a comprehension.

### PN102: hooks only run in components and custom hooks

`PN102` flags a hook called at module level, in a plain function, or in
a method:

```python
theme = pn.use_theme()  # PN102: at module level


def header():
    count, _ = pn.use_state(0)  # PN102: 'header' isn't a component
    return pn.Text(str(count))
```

Decorate the function with `@pn.component`, or rename it `use_*` if
it's meant to be a custom hook. A hook inside a function nested in a
component, such as an event handler, is `PN101` instead, because the
handler doesn't run during render.

### PN103: dependency lists must be complete

For `use_effect`, `use_layout_effect`, `use_memo`, `use_callback`, and
`use_focus_effect`, `PN103` compares the names the callback reads with
the dependency list. It only checks a call when the list is a literal
list or tuple and the callback is a lambda or the name of a function
defined in the same component or custom hook.

```python
@pn.component
def Profile(user_id: int) -> pn.Node:
    user, set_user = pn.use_state(None)

    async def load():
        set_user(await fetch_user(user_id))

    pn.use_effect(load, [])  # PN103: reads 'user_id'
    ...
```

With `[]`, the effect loads the first user forever. List every
component-scoped name the callback reads, here `[user_id]`.

A name only needs to be listed when the component or custom hook binds
it: a parameter, a local assignment (including tuple unpacking), or a
nested function. These are exempt:

- names defined at module level, and builtins
- the setter from `value, set_value = pn.use_state(...)` and the
  dispatcher from `state, dispatch = pn.use_reducer(...)`
- names assigned from `pn.use_ref(...)` or `pn.use_animated_value(...)`
- names assigned from `pn.use_memo(...)` or `pn.use_callback(...)` with a
  literal empty dependency list, which are computed once
- names bound by an import inside the component

The state value itself isn't exempt, and a setter or ref stops being
exempt if the name is assigned again somewhere else in the component.

Reading an attribute counts as reading its root name, so
`props.title` needs `props` in the list. Listing `props.title` also
satisfies it: a dependency covers every name it mentions.

`PN103` doesn't check a call whose dependency list is omitted, `None`,
or built at runtime (`deps`, `list(xs)`), and it skips callbacks it
can't see into, such as `make_handler(x)`.

The finding is reported on the line of the dependency list.

### PN104: user components take keys through `.with_key()`

User components don't accept `key=`: the parameters come from your
function's signature, so there's nowhere for the key to go. `PN104`
flags `key=` in a call to a module-level `@component` defined in the
same file:

```python
@pn.component
def Row(item: Item) -> pn.Node:
    return pn.Text(item.title)


pn.Column(*[Row(item, key=item.id) for item in items])  # PN104
```

Key the element instead:

```python
pn.Column(*[Row(item).with_key(item.id) for item in items])
```

Built-in elements like `pn.View(key=...)` are fine. A component
can't declare a parameter named `key` at all: `@pn.component` raises
`TypeError` for one, and calling a component with `key=` raises
`TypeError` at run time too.

### PN000: the file couldn't be read

A file with a syntax error, or one that isn't valid UTF-8, produces a
single `PN000` finding. The linter doesn't check the rest of it.

## Suppressing a finding

Add a `# pn: ignore` comment to the line the finding is reported on.
Name the codes in brackets to silence only those:

```python
config = pn.use_memo(build_config, [])  # pn: ignore[PN103]
pn.use_effect(lambda: x, [])  # pn: ignore[PN101,PN103]
legacy = pn.use_state(0)  # pn: ignore
```

Prefer the bracketed form so that a new problem on the same line still
shows up. `PN000` can't be suppressed.

## Limits

The linter works on one file at a time and doesn't infer types, so:

- It recognizes components by their decorator and hooks by their name.
  A component created some other way, or a hook imported under an
  alias that doesn't start with `use_`, isn't recognized.
- `PN104` only knows about components defined at module level in the
  same file.
- `PN103` treats every local value as changing between renders. A
  value that you know is stable, such as a `use_memo(..., [])` result,
  still has to be listed or suppressed.
- It doesn't follow control flow: a hook after
  `if not ok: raise ValueError(...)` is fine, but one after
  `if not ok: return None` is flagged.

## Next steps

- Read why the rules exist in [Hooks](../concepts/hooks.md).
- See the full API in [Lint](../api/lint.md).
