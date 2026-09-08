# Lists

Render a dynamic list with [`FlatList`][pythonnative.FlatList], use
keys for stable reconciliation, and hook in delete and toggle actions.
This example builds a simple to-do list.

Paste it into `app/main.py` of a project scaffolded with `pn init`,
then run `pn preview app.main.TodoList`.

## The code

```python
import pythonnative as pn


@pn.component
def TodoRow(todo, on_toggle, on_delete):
    return pn.Row(
        pn.Switch(value=todo["done"], on_change=lambda v: on_toggle(todo["id"])),
        pn.Text(
            todo["title"],
            style={
                "flex": 1,
                "font_size": 16,
                "color": "#888" if todo["done"] else "#000",
            },
        ),
        pn.Button("Delete", on_press=lambda: on_delete(todo["id"])),
        style={"spacing": 12, "padding": 8, "align_items": "center"},
    )


@pn.component
def TodoList():
    todos, set_todos = pn.use_state(
        [
            {"id": "1", "title": "Try PythonNative", "done": True},
            {"id": "2", "title": "Build a real app", "done": False},
            {"id": "3", "title": "Profit", "done": False},
        ]
    )
    draft, set_draft = pn.use_state("")

    def add():
        title = draft.strip()
        if not title:
            return
        new_id = str(max(int(t["id"]) for t in todos) + 1) if todos else "1"
        set_todos([*todos, {"id": new_id, "title": title, "done": False}])
        set_draft("")

    def toggle(todo_id):
        set_todos(
            [
                {**t, "done": not t["done"]} if t["id"] == todo_id else t
                for t in todos
            ]
        )

    def delete(todo_id):
        set_todos([t for t in todos if t["id"] != todo_id])

    return pn.Column(
        pn.Row(
            pn.TextInput(
                value=draft,
                on_change=set_draft,
                placeholder="What needs doing?",
                style={"flex": 1},
            ),
            pn.Button("Add", on_press=add),
            style={"spacing": 8, "padding": 16},
        ),
        pn.FlatList(
            data=todos,
            render_item=lambda t: TodoRow(
                todo=t, on_toggle=toggle, on_delete=delete, key=t["id"]
            ),
            key_extractor=lambda t: t["id"],
            style={"flex": 1},
        ),
    )
```

## Why keys matter

The reconciler matches children by `key` first and by position only as
a fallback. Without keys, a delete of the first row would update the
remaining rows in place (showing the wrong text briefly) before
unmounting the last row. With keys, identity flows from the data, so
"todo 2" stays mounted as "todo 2" even when its index shifts.

The `key_extractor` on `FlatList` and the `key=` on the rendered row
both come from the same `todo["id"]`. When in doubt: use a stable
identifier that's part of the data, not the position.

## Performance notes

- `FlatList` lazily mounts only the rows that are visible (or near
  visible); off-screen rows are represented by spacers and the window
  shifts as the user scrolls. For long lists it scales much better
  than wrapping a `Column` in a `ScrollView`.
- Avoid recomputing `data` on every render. If you derive it from
  another piece of state, wrap it in
  [`use_memo`][pythonnative.use_memo].
- For row callbacks that you pass deeply, consider
  [`use_callback`][pythonnative.use_callback] to keep references
  stable.

## Sorting and filtering

Sorting and filtering are pure functions over the `todos` array; do
them at render time:

```python
visible = [t for t in todos if not hide_done or not t["done"]]
visible.sort(key=lambda t: t["title"])
```

If the input list is large, memoize the result:

```python
visible = pn.use_memo(
    lambda: sorted([t for t in todos if not hide_done or not t["done"]],
                   key=lambda t: t["title"]),
    [todos, hide_done],
)
```

## Next steps

- Capture user input: [Forms](forms.md).
- Move the to-do list onto its own screen: [Navigation](navigation.md).
- Persist between launches with the file system: [Native modules](../guides/native-modules.md).
