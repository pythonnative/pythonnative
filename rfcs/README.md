# PythonNative RFCs

An RFC (request for comments) is a short design document for a change that
is too large, too cross-cutting, or too hard to reverse to be explained by a
commit message alone. The `rfcs/` directory is the durable record of those
decisions: what was changed, why, what alternatives were rejected, and what
was deliberately left out.

RFCs exist to give humans and coding agents a shared starting point. A new
session (or a new contributor) should be able to read the accepted RFCs and
understand why the code looks the way it does without replaying old chat
transcripts or pull-request threads.

## When an RFC is required

Write an RFC before implementing a change that does any of the following:

- Adds or removes a public `pythonnative` API surface (a component, a hook,
  a module facade, a CLI subcommand, or a `pythonnative.toml` table).
- Changes the wire contract between Python and the native runtimes
  (`PROTOCOL_VERSION`, a component schema, a native module method).
- Changes a project convention that apps depend on (directory layout,
  build staging, asset resolution, entry points).
- Touches more than one of Python, Swift, Kotlin, and the browser preview at
  once.
- Removes a feature or replaces one design with another.

Bug fixes, refactors that preserve behavior, documentation, and additions
confined to one layer don't need an RFC. When in doubt, write a short one;
an RFC can be a single page.

## Lifecycle

An RFC moves through these states, recorded in its header:

| Status | Meaning |
| --- | --- |
| `Draft` | Being written. May change freely. |
| `Accepted` | Approved for implementation. The design is settled; details may still shift during implementation and are recorded in the RFC before merge. |
| `Implemented` | Shipped. The header lists the pull request(s) and the release. |
| `Superseded` | Replaced by a later RFC, which is linked from the header. |
| `Withdrawn` | Abandoned before implementation, with the reason noted. |

While the project is pre-1.0 and has a single maintainer, "accepted" means
the maintainer agreed to the plan in the discussion that produced the RFC.
The RFC still gets written first, because the point is the record, not the
ceremony.

## Process

1. Copy `0000-template.md` to `NNNN-short-title.md`, where `NNNN` is the
   next unused number. Use lowercase words separated by hyphens.
2. Fill in every section. Delete the guidance comments. Keep the "Design"
   section concrete: name the modules, the props, the wire fields, and the
   files that change.
3. Open a pull request containing only the RFC when the change needs
   review before implementation begins. For work that is agreed on
   informally, the RFC may land in the same pull request as the
   implementation, with status `Implemented`.
4. Update the RFC as the implementation teaches you something. The
   document that lands should describe what shipped, not what was
   planned.
5. When a later RFC replaces a decision, mark the old one `Superseded`
   and link both directions.

## Writing guidelines

- Follow the documentation style in `AGENTS.md`: Chicago Manual of Style
  grammar, straight quotes, no em dashes, contractions where they read
  naturally.
- Lead with the problem. A reader should understand what's broken or
  missing before reading a single API name.
- Compare with the reference implementation ("what does React Native do?")
  and say where PythonNative deliberately differs and why.
- List removals explicitly. Pre-1.0, replacing code is preferred over
  keeping compatibility shims, and the RFC is where that removal is
  justified.
- Include a "Non-goals" section. Half the value of an RFC is knowing what
  it decided not to do.

## Index

| Number | Title | Status |
| --- | --- | --- |
| [0001](0001-assets-and-visual-primitives.md) | Assets and visual primitives | Implemented |
| [0002](0002-core-parity-and-correctness.md) | Core parity and correctness | Implemented |
| [0003](0003-incremental-rendering-and-lists.md) | Incremental rendering and lists | Implemented |
