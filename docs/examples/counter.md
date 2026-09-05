# Counter

A counter with two buttons (increment and decrement), a reset, and a
small bit of conditional styling. Practical introduction to
[`use_state`][pythonnative.use_state] and event handlers.

Paste it into `app/main.py` of a project scaffolded with `pn init`,
then run `pn preview app.main.Counter`.

## The code

```python
import pythonnative as pn


@pn.component
def Counter(initial: int = 0):
    count, set_count = pn.use_state(initial)

    inc = lambda: set_count(count + 1)
    dec = lambda: set_count(count - 1)
    reset = lambda: set_count(initial)

    color = "#0a84ff" if count >= 0 else "#ff3b30"

    return pn.Column(
        pn.Text(
            f"Count: {count}",
            style={"font_size": 28, "bold": True, "color": color},
        ),
        pn.Row(
            pn.Button("-", on_press=dec, style={"flex": 1}),
            pn.Button("+", on_press=inc, style={"flex": 1}),
            style={"spacing": 8},
        ),
        pn.Button("Reset", on_press=reset),
        style={
            "spacing": 12,
            "padding": 16,
            "align_items": "stretch",
        },
    )
```

## Notable bits

- `inc`, `dec`, `reset` are simple closures that capture `count` and
  `initial`. They are recreated on every render but the reconciler
  doesn't care; only behavior, not identity, matters here.
- `style` arguments are plain dicts. Layout properties (`flex`,
  `spacing`, `padding`, `align_items`) sit beside visual properties
  (`color`, `font_size`, `bold`).
- The `Row` uses `flex: 1` on its children to split space evenly. The
  same `flex` knob works inside `Column`s for vertical layouts.

## Stable handlers (optional)

If you find yourself passing the handlers down to deeply nested
components and the renders are getting expensive, switch to
[`use_callback`][pythonnative.use_callback]:

```python
inc = pn.use_callback(lambda: set_count(count + 1), [count])
```

That keeps the function reference stable for any equal `count` and
gives memoized children a chance to skip re-rendering. For a small
top-level component like this one, the closure version is fine.

## Reducer flavor

For more complex counters (with bounds, multipliers, history), reach
for [`use_reducer`][pythonnative.use_reducer]:

```python
def reducer(state, action):
    if action == "inc":
        return state + 1
    if action == "dec":
        return state - 1
    if action == "reset":
        return 0
    raise ValueError(f"unknown action: {action!r}")


@pn.component
def Counter():
    state, dispatch = pn.use_reducer(reducer, 0)
    return pn.Column(
        pn.Text(str(state), style={"font_size": 28}),
        pn.Row(
            pn.Button("-", on_press=lambda: dispatch("dec")),
            pn.Button("+", on_press=lambda: dispatch("inc")),
            style={"spacing": 8},
        ),
        pn.Button("Reset", on_press=lambda: dispatch("reset")),
        style={"spacing": 12, "padding": 16, "align_items": "stretch"},
    )
```

The reducer is a plain function: easy to test, easy to read.

## Next steps

- Capture and submit user input: [Forms](forms.md).
- Render dynamic data: [Lists](lists.md).
- Move between screens: [Navigation](navigation.md).
