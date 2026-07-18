---
name: edict
description: Turn a raw maintainer request into an implementation-ready GitHub issue via a structured interview — research the repo, ask decision-shaped questions, draft a requirements-first spec, file it immediately as a draft-labeled issue, then revise it in place until the maintainer approves and the `draft` label comes off. Use whenever the maintainer says "file an issue", "put this on my list", "track this", "add to the roadmap", or states a request/idea they want captured for later implementation — even a one-liner.
---

# /edict — request → implementation-ready issue

The maintainer sends a request (often terse, possibly from a phone). Your job is to refine it
into a GitHub issue that a **different agent, with no access to this conversation**, can
implement cold. The issue is the entire handoff: if a fact lives only in this chat, it's lost.

This skill files issues; it never implements them. Implementation happens later when the
maintainer says "implement issue X".

The issue is the only format. There is no side artifact, no separate archive, no parallel
numbering scheme — the GitHub issue number is the identifier, allocated atomically by GitHub,
so any number of edicts can run in parallel without coordination. Review happens on the issue
itself: it is filed immediately with a `draft` label, revised in place, and becomes real when
the label comes off.

Two principles from the research this skill is built on:

- **Specify behavior and constraints, not implementation.** The implementing agent will have
  fresh code context and should choose the how. Constraints matter more than requirements —
  they prevent reasonable-but-wrong choices ("don't break X", "must stay zero-dependency").
- **Every acceptance criterion must be testable.** If you can't imagine the test or the
  observable check, it's a wish, not a criterion — sharpen it or drop it.

## Step 1 — Restate and ground (before asking anything)

1. Restate the request as one sentence of intent. If you can't, that's your first interview
   question.
2. **Research the repo first.** Read the code the request touches, related ADRs, docs pages,
   and CLAUDE.md constraints. Search existing issues for duplicates/overlap — GitHub MCP
   `search_issues`/`list_issues`, or `gh issue list --search "..." --state all` where the CLI
   exists. Never ask the maintainer something the repo already answers — informed questions
   are the whole value of the interview.
3. If an existing issue substantially covers it, propose updating that issue instead of filing
   a duplicate.

## Step 2 — Size the request

- **S** — unambiguous, one obvious change, no open decisions (e.g. "rename this flag",
  a clear bug with a repro). → Skip the interview, or ask at most one confirming question.
- **M/L** — any open design decision, scope ambiguity, tradeoff, or anything touching a
  flagged/public surface. → Interview.

When a request is really several requests, say so and propose the split before interviewing —
one issue per independently implementable outcome.

## Step 3 — Interview (adaptive, capped)

Use `AskUserQuestion`. Hard rules, tuned for answering from a phone:

- **The interview is mandatory for M/L requests — a failed tool call is not a skip.** If an
  `AskUserQuestion` call errors (e.g. "permission stream closed", a transient harness/MCP
  fault), **retry it** — same questions — rather than silently defaulting every answer and
  proceeding. Retry up to 3 times; if it still won't go through, do **not** invent decisions:
  post the questions as plain text and wait for the maintainer's reply before drafting the
  Decisions table. The same rule applies to the Step 5 approval gate — never remove the `draft`
  label on a failed/absent gate; retry, then fall back to a plain-text confirmation. Defaulting
  is only for decisions with a conventional answer, never a substitute for an interview the
  tooling failed to deliver.
- At most **2 rounds**, ≤4 questions each. If more than ~6 decisions are genuinely open, the
  request is underbaked — say which decisions you defaulted and let the draft review catch
  wrong calls.
- Every question is **decision-shaped**: concrete options with consequences spelled out, your
  recommended option **first** and labeled "(Recommended)". Never an open-ended essay question —
  "Other" exists for free text if the maintainer wants it.
- Ask only questions whose answer **changes the issue body**. Scope boundaries, tradeoffs,
  user-visible behavior, priorities between conflicting goals: yes. Anything with a
  conventional default or answerable from the repo: no — pick it and record it as a default.
- Record every answer (and every default you chose) — they become the **Decisions** table.

## Step 4 — Draft the issue (requirements-first)

Title: what the repo's style dictates (see plumbing section). Body template — omit sections
that would be empty rather than padding them:

```markdown
## Summary
<2–4 sentences: the problem as it exists today, and the desired outcome as observable
behavior. Code snippet of before/after if it clarifies.>

## Motivation
<Why this matters and why now. Concrete evidence: file refs, error output, the friction
observed. Not marketing.>

## Decisions (locked, YYYY-MM-DD)
<Only when an interview happened. Table: | Question | Decision |. Include defaults you
chose, marked "(default, not asked)". These are settled unless explicitly reopened.>

## Constraints & non-goals
<What the implementer must NOT do or change; explicitly out-of-scope things a reasonable
agent might otherwise fold in. This section prevents reasonable-but-wrong choices.>

## Pointers
<Repo-relative file/line refs to the code involved, related issues/ADRs/docs pages, and
repo-specific rules that bind this work (mirror rules, test systems, versioning). Everything
the implementing agent needs to start without a scavenger hunt.>

## Acceptance criteria
<Each one testable/observable. Behavior, not implementation. Include the quality gates that
must stay green.>

## Plan
<OPTIONAL — only when the interview surfaced real sequencing or scoping phases. Otherwise
omit: planning belongs to the implementing agent at implementation time.>
```

Writing rules:

- Exact names, paths, versions — never "the config" when you mean a specific file.
- Self-sufficient: no "as discussed", no reference to this conversation.
- Note versioning/process implications the repo defines (see plumbing) — e.g. whether the
  change needs an ADR or lands as minor vs patch.

## Step 5 — File as draft, then gate

File the issue **immediately** — final title, full body, its intended labels **plus
`draft`**. The `draft` label is the review state: while it's on, the issue is a proposal the
maintainer is still free to reshape or throw away; nothing downstream should treat it as
committed work. The issue on github.com is the review surface — phone-friendly, durable, and
visible to any session — so the maintainer reviews the real thing, not chat text.

1. **Create the issue** with the `draft` label (GitHub MCP `issue_write`, or `gh issue create`
   where the CLI exists).
2. **Post the issue URL in chat**, then gate with one `AskUserQuestion`:
   - **Approve (Recommended)** — proceed to Step 6.
   - **Revise** — the maintainer says what, by chat or by commenting on the issue itself.
     Edit the issue body/title/labels in place and gate again. Repeat as needed; the issue
     number never changes.
   - **Discard** — close the issue as `not_planned`. No residue to clean up.

   Never remove the `draft` label without this gate (retry rules in Step 3 apply).

## Step 6 — Finalize

Remove the `draft` label. That's the whole promotion: the issue number, title, and URL are
already final, and the project board picks the issue up on its own (the board's auto-add
workflow — see plumbing — means the skill does zero board work). Reply with the issue URL and
a one-line restatement of what was captured.

## Epic edicts — linking a family of issues

Some requests are one outcome; some are a *program* of many independently-implementable
outcomes (a roadmap, a curriculum, a migration touching N sites). Step 2 already says to split
those — this is how to split them **and keep them connected**, so each child is a cold-start
issue while the whole still reads as one plan.

- **File an epic issue + one child issue per outcome, all as drafts in one batch.** Issue
  numbers come from GitHub, so there's no numbering to coordinate — file the epic first so the
  children can link back to its number.
- **The epic issue is the tracker.** Its body carries the shared context — the philosophy, the
  scheme, the tiered sequence — and a **checklist that links out to every child**
  (`- [ ] <name> — #<issue>`). Label it `roadmap`. It does *not* restate each child's spec.
- **Each child issue is fully self-contained.** A cold agent implements it from the child alone
  (Step 4 template in full). The child links back to the epic in its `## Pointers`
  ("Part of the <epic> roadmap, #<epic-issue>"); the epic never holds the child's only copy of a
  fact. Duplicate the *minimum* shared context each child needs (don't make children read the
  epic to be implementable) — self-sufficiency wins over DRY here.
- **Link them natively.** Attach each child as a **GitHub sub-issue of the epic**
  (`mcp__github__sub_issue_write`, or `gh` where available) so the parent/child tree is real,
  not just prose.
- **Gate once over the batch.** Point the maintainer at the epic (its checklist reaches every
  child) and run the Step 5 gate on the set as a whole; per-child revisions are in-place edits
  like any other draft. On approval, remove the `draft` label from the epic and every child.

---

## Repo plumbing — pymediate (swap this section when porting the skill to another repo)

- **Titles are plain descriptive sentences** — Conventional Commits applies to PR titles,
  not issues.
- **Labels:** `draft` marks an issue still in the Step 5 review loop — it must come off only
  via the gate. Otherwise `roadmap` for feature/process work; `bug`, `documentation`,
  `process` where they fit better.
- **Board:** user-level project **#2 "pymediate"**
  (<https://github.com/users/sina-al/projects/2>) is populated by the Project's built-in
  **auto-add workflow** (new issues land with Status = Todo) — the skill does no board
  plumbing at all. Leave Priority unset unless told.
- **House style exemplar:** issue #39 (decisions table from maintainer interview, phased
  checklists, testable acceptance criteria). #44 is the requirements-first shape.
- **Repo rules that frequently become Constraints/Pointers entries:**
  - Async/sync mirror: `pymediate` (async, top-level) and `pymediate.sync` are structural
    mirrors — changes to one side must consider the other.
  - The typing-snippet system (`tests/typing/snippets/{valid,errors}/`) and its exact bar —
    never suggest "fixing" `errors/` snippets.
  - Docstring policy: public docstrings mirror `docs/content/docs/api/*.mdx`; examples must run.
  - Versioning (ZeroVer): minor = public-API break or new feature; patch = everything else.
    Flag when the change touches `__all__`, `RequestHandler`, or `ServiceProvider` (ADR likely).
  - `examples/` run against the *released* package — example updates are post-release
    follow-ups via the `example` skill.
  - All verification via `poe` tasks, never bespoke tool invocations.
