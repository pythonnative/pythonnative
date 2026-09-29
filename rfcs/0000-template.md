# RFC NNNN: Title

- Status: Draft
- Author(s): Name
- Created: YYYY-MM-DD
- Implemented in: (pull request links, once shipped)
- Supersedes / Superseded by: (links, or "none")

## Summary

One paragraph. What changes, for whom, and why it matters.

## Motivation

What's broken, missing, or awkward today? Show the code a user has to write
now, or the thing they can't build. Reference issues and prior discussion.

## Reference behavior

What does React Native (or the relevant platform) do for this problem?
Where does this RFC follow it, and where does it deliberately differ in
order to stay Pythonic?

## Design

The concrete proposal. Cover each layer that changes:

- Python API: modules, functions, dataclasses, type aliases, signatures.
- Wire contract: new or changed component props, module methods, events,
  and whether `PROTOCOL_VERSION` changes.
- Native runtimes: Swift and Kotlin behavior, including platform limits.
- Browser preview: how the same contract renders in the dev server.
- Tooling: CLI, builder, dev server, codegen, tests, docs.

Include short code samples for the user-facing API.

## Removals

What existing code, props, conventions, or documentation are deleted, and
why compatibility shims aren't kept.

## Alternatives considered

Each rejected option with a sentence or two on why it lost.

## Non-goals

What this RFC intentionally leaves for later, so nobody wonders whether it
was forgotten.

## Testing and rollout

How the change is verified (unit, native, E2E, docs build), and any
migration notes for the examples and templates.

## Open questions

Anything unresolved at the time of writing. Remove the section once the
RFC is implemented, or convert each item into a decision.
