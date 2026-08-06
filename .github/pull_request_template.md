## Description

<!-- Explain WHY this change is needed, not just WHAT it does. Link related issues. -->

## Changes

<!-- Brief bullet points of what changed -->

-

## Task

<!-- The task ID from specs/<feature>/tasks.md, e.g. T042. Omit for work outside a spec. -->

Closes: T

## PR Checklist

- [ ] **Article VI** — CHANGELOG.md updated under `[Unreleased]`, or this PR changes
      no behaviour (refactor, test-only, docs) and says so in Description
- [ ] **Article IV** — all variable and function names are self-documenting (no
      single-letter names); booleans read as `is`/`has`/`can`/`should`/`was`;
      functions stay under 40 lines; every file opens with a purpose comment and
      every exported function carries a doc comment
- [ ] Code comments explain the "why" and are readable by a non-developer
- [ ] **Article V** — the failing test was written first, and the three layers stay
      separate: unit fully mocked and under 10 ms, integration on real
      infrastructure, UX through `run-dev-clean.ps1` with real events
- [ ] **Article IX** — no secret appears in code, config, a test fixture, or a log
- [ ] **Article VII** — anything custom a framework could have provided carries a
      one-line justification at the component
- [ ] **Article III** — branch follows naming convention (feature/*, fix/*, chore/*, docs/*)

## Testing

<!--
Article X: "it compiles" and "the API returned 200" are not proof.
Paste the test output, the created Omi conversation, the measured timing —
whatever demonstrates the behaviour actually works.
-->

## Quality Mode: BEST

<!-- Confirm multi-agent approach was used where applicable -->
- [ ] Sub-agents leveraged for parallelizable work
- [ ] Appropriate model tier used for task complexity

