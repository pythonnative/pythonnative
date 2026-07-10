# Documentation style guide

This page describes how PythonNative's documentation and source-level
docstrings are written. Follow it when authoring new code or revising
existing pages so the site renders consistently and `help()` reads
cleanly inside a Python REPL on a developer machine or device.

## TL;DR

- Use **Google-style** docstrings everywhere (modules, classes, functions).
- Let type hints carry the types. Don't repeat them inside docstrings.
- Use Material **admonitions** (`!!! tip "Title"`) for callouts in
  Markdown, not plain `>` blockquotes.
- Cross-link API symbols using mkdocstrings autorefs:
  `` [`use_state`][pythonnative.use_state] ``.
- Comments explain **why**, not **what** (the code already says what).

## Grammar and punctuation

We follow the *Chicago Manual of Style* (17th edition) for prose. Highlights:

- **No em dashes (`—`).** Use commas, parentheses, semicolons, colons, or
  full sentences instead. The exact replacement depends on context: use a
  pair of commas for a brief aside, parentheses for a longer one, a colon
  before a list or amplification, and a semicolon between two related
  independent clauses.
- **Use straight ASCII quotes and apostrophes** (`"` and `'`), not curly
  quotes (`“`, `”`, `‘`, or `’`). This keeps prose copy-pasteable into
  source code, terminals, and search.
- Use the **serial (Oxford) comma** in lists of three or more.
- Spell out **e.g.** and **i.e.** with periods and follow them with a
  comma: `e.g., a counter component`.
- Hyphenate compound modifiers before a noun (`cross-platform toolkit`,
  `single-page application`) but not after (`the toolkit is cross platform`).
- Use **sentence case** for headings and titles: only the first word and
  proper nouns are capitalized.

## Docstrings: Google style

PythonNative follows the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
The `mkdocstrings` plugin is configured for Google style and renders
the standard sections as tables.

### Function or method

```python
def use_state(initial=None):
    """Return ``(value, setter)`` for component-local state.

    State persists across re-renders of the same component instance.
    The setter accepts a value or a ``current -> new`` callable; calling
    it with an unchanged value is a no-op.

    Args:
        initial: The initial state value. If callable, it is invoked
            once on first render (lazy initialization).

    Returns:
        A 2-tuple ``(value, setter)`` where ``value`` is the current
        state and ``setter`` updates it (and triggers a re-render).

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Counter():
            count, set_count = pn.use_state(0)
            return pn.Button(
                f"Count: {count}",
                on_press=lambda: set_count(count + 1),
            )
        ```
    """
```

Notes:

- The first line is an **imperative summary** ending in a period.
- Leave one blank line between the summary and the extended description.
- Use these sections in order: `Args:`, `Returns:`, `Yields:`, `Raises:`,
  `Note:`, `Warning:`, `Example:`. Skip any that don't apply.
- **Don't repeat type annotations** inside `Args:`; the rendered API
  table pulls them from the function signature automatically.
- Inside `Example:`, use a fenced code block (` ```python `) with the
  imports needed to run the snippet so users can copy it directly.

### Class

```python
class Element:
    """Immutable description of a single UI node.

    An ``Element`` is a lightweight descriptor: a type plus props plus
    children. No native views are created until the reconciler mounts
    the tree.

    Attributes:
        type: A string for built-in elements (``"Text"``, ``"Button"``)
            or a callable for ``@component`` function components.
        props: Dict of properties passed to the native handler.
        children: Ordered list of child ``Element`` instances.
        key: Optional stable identity for keyed reconciliation.

    Example:
        ```python
        from pythonnative import Element

        node = Element("Text", {"text": "Hello"}, [])
        ```
    """
```

The class summary describes the type's purpose. Document construction in
`__init__` only when there is more to say than the signature already conveys
(set `merge_init_into_class: true` in mkdocstrings; already configured).

### Module

Every module should open with a one-line summary, an extended description,
and (when illustrative) a small example:

```python
"""Hook primitives for function components.

Provides React-like hooks for managing state, effects, memoization,
context, and navigation within ``@component`` functions. Hooks must
be called at the top level of a component (not inside conditionals
or loops) so they can be matched to the same slot across renders.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Counter(initial=0):
        count, set_count = pn.use_state(initial)
        return pn.Button(
            f"Count: {count}",
            on_press=lambda: set_count(count + 1),
        )
    ```
"""
```

### Private helpers

Underscore-prefixed members (`_helper`) are filtered out of the public
API site (mkdocstrings `filters: ["!^_"]`). Keep their docstrings
short (one line is usually enough), but do write them: contributors
inspect them in editors and during code review.

## Comments: explain *why*

!!! quote "Rule of thumb"
    Comments are most useful when they explain things the reader cannot
    learn from the code itself.

Good comments:

- Document a non-obvious invariant or constraint.
- Explain a trade-off between two reasonable approaches.
- Cite an external spec, RFC, Android/iOS API doc, or upstream bug report.
- Warn about a subtle ordering requirement (e.g., effects must be queued
  during render and flushed after commit).

Bad comments (don't add them):

- Narrating what the next line does (`# increment counter`).
- Restating the function name (`# create the page`).
- TODOs without an owner or issue link; open a tracking issue and link it.

When you find a redundant comment during a refactor, delete it. The
diff will be smaller and the code will be easier to read.

## Markdown: admonitions over blockquotes

Use Material admonitions for callouts. They render with an icon, a
colored block, and a collapsible variant:

```markdown
!!! note
    Plain note.

!!! tip "Pro tip"
    Custom-titled tip.

!!! warning
    Heads-up about a footgun.

??? info "Click to expand"
    Collapsed by default.
```

Reserve plain Markdown blockquotes (`>`) for *quoted text* (a quote
from the docs, a user, or an upstream project). Don't use them for
tips or warnings.

## Cross-linking

Mkdocstrings plus autorefs lets you link to any documented symbol from
plain Markdown. Prefer these short forms:

```markdown
The [`use_state`][pythonnative.use_state] hook returns a ``(value, setter)``
tuple. See [`Element`][pythonnative.Element] for the underlying descriptor
type and [`NavigationContainer`][pythonnative.NavigationContainer] for
the root of a navigation tree.
```

Inside a docstring, plain backticks plus the qualified name are
typically enough; autorefs picks them up via signature annotations
(`signature_crossrefs: true`).

## Code samples

- Always tag the language: ` ```python `, ` ```bash `, ` ```kotlin `,
  ` ```swift `, ` ```yaml `.
- Prefer **runnable** snippets that include the imports needed to
  copy-paste them.
- For longer multi-step examples, lean on Material's `pymdownx.tabbed`
  to show the same example in different forms (e.g., "Android" vs.
  "iOS").

## Page structure

A typical concept or guide page follows this skeleton:

1. `# Title`. H1 only on the page itself; the site nav supplies the
   parent heading.
2. **One-paragraph summary** of what this page covers and who it's for.
3. **Sections** (`##`, `###`) covering the topic in order of increasing
   depth. Lead with the simplest example.
4. **Next steps** at the bottom with cross-links to related pages,
   to keep the reader moving.

```markdown
## Next steps

- Build your first component: [Components](components.md)
- Manage app state: [`use_reducer`][pythonnative.use_reducer]
- Run on a device: [Android guide](../guides/android.md)
```

## Linting

Docstrings are checked by Ruff with the Google convention enabled:

```bash
ruff check src/pythonnative
```

The relevant rule set lives in `pyproject.toml` under `[tool.ruff.lint]`.
The site build also runs in **strict mode** (`mkdocs build --strict`)
on every push and pull request, so missing cross-references and broken
links fail CI.
