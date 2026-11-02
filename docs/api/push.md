# Push

[`Push`][pythonnative.push.Push] registers for remote push and reports tokens and
messages. It needs the `notifications` capability too, so use
`use = ["notifications", "push"]` under `[plugins]`, with `notifications = true` and
`remote_notifications = true` under `[permissions]`. See the
[Push guide](../guides/capabilities/push.md).

::: pythonnative.push
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]
