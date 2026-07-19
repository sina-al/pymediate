---
name: adr
description: Scaffold a new numbered Architecture Decision Record in docs/adr/ following this repo's existing template (Context, Investigation/Proposed Solutions, Pros/Cons, Decision, Consequences). Use when starting work on a nontrivial design or public-API change in pymediate.
---

# /adr — scaffold a new ADR

Use this when starting work on a design decision worth recording: changes to public API shape
(`__all__`, `RequestHandler`, `Request`, `PipelineBehavior`, resolver protocols), generics/typing
design, or anything CI's breaking-change checks would flag.

**Scope: the package only.** ADRs record decisions about pymediate *the package* — its public
API, generics/typing, runtime semantics, and breaking changes. A decision about CI, release
pipelines, or repo/docs tooling does **not** get an ADR: document it in the operational doc that
owns that area (`OPERATIONS.md`, `examples/README.md`, the relevant workflow comments, or a skill
doc) instead. If the request is pipeline- or tooling-shaped, redirect there rather than
scaffolding a file here.

## Steps

1. **Determine the next number.** List `docs/adr/*.md`, take the highest `NNNN` prefix, increment
   it (zero-padded to 4 digits, e.g. `0001` → `0002`).
2. **Get the title** from the user's request (a short noun phrase describing the decision), and
   slugify it for the filename: `docs/adr/NNNN-kebab-case-title.md`.
3. **Fill the template** below. Use today's date (`YYYY-MM-DD`). Default `Author:` to `Claude`
   and `Reviewers:` to `@sina-al` (the repo owner's GitHub handle) unless told otherwise.
   `Status:` starts as `Proposed`.
4. **Write the file**, then tell the user the path and next-number so they can review.

Do not mark an ADR `Accepted` yourself — leave `Status: Proposed` for the human reviewer to
change once they've read it.

## Template

```markdown
# ADR NNNN: <Title>

**Status:** Proposed
**Date:** <YYYY-MM-DD>
**Author:** Claude
**Reviewers:** @sina-al

## Context

<What problem/tension prompted this? Include a minimal code example of the current behavior
and why it's insufficient.>

## Proposed Solution(s)

<One or more options. For each: the design (code sketch), then Pros/Cons. If there's a clear
recommendation, mark it "RECOMMENDED" and say why; otherwise lay out the tradeoff plainly.>

## Decision

<Which option, and the rationale in a few bullet points.>

## Consequences

### Positive
- ...

### Negative
- ...

## Migration Path

<Only if this is a breaking change — otherwise state "No migration needed" explicitly.>

## Open Questions

<Anything left unresolved, framed as a question with a tentative lean.>
```
