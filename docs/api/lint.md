# Lint

Static checks for the rules of hooks. `pn lint` is a thin wrapper
around this module: [`lint_paths`][pythonnative.lint.lint_paths] finds
and checks the files, and [`lint_source`][pythonnative.lint.lint_source]
checks one module's text. Both return
[`Finding`][pythonnative.lint.Finding] objects, so you can run the same
checks from a test or an editor integration.

```python
from pythonnative.lint import lint_paths

for finding in lint_paths(["app"]):
    print(finding.format())
```

See the [Linting guide](../guides/linting.md) for what each rule
catches and how to suppress a finding.

::: pythonnative.lint
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Run the checks from the command line with `pn lint`: see
  [CLI (`pn`)](cli.md).
- Read why the rules exist in [Hooks](../concepts/hooks.md).
