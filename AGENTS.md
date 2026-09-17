# AGENTS.md

Follow Chicago Manual of Style (CMOS) grammar in the documentation, but use straight apostrophes and quotation marks, avoid em dashes, and use contractions where appropriate.

## RFCs

Major changes are designed in `rfcs/` before they're implemented. Read `rfcs/README.md` for the rules, and read the accepted RFCs before proposing a change that overlaps one of them. In short:

- Write an RFC (copy `rfcs/0000-template.md`) before adding or removing public API, changing the Python-to-native wire contract, changing a project convention apps depend on, or touching Python, Swift, Kotlin, and the browser preview at once.
- Keep the RFC honest: update it as the implementation changes, list removals explicitly, and land it with status `Implemented` in the same pull request as the code when the plan was agreed on informally.
- Bug fixes, behavior-preserving refactors, and single-layer additions don't need one.
