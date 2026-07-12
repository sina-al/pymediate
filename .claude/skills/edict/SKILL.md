---
name: edict
description: Turn a raw maintainer request into an implementation-ready GitHub issue via a structured interview — research the repo, ask decision-shaped questions, draft a requirements-first spec, render it as a branded EDICT artifact for review, then file and board it (the EDICT is archived uncommitted in the Claude project folder). Use whenever the maintainer says "file an issue", "put this on my list", "track this", "add to the roadmap", or states a request/idea they want captured for later implementation — even a one-liner.
---

# /edict — request → implementation-ready issue

The maintainer sends a request (often terse, possibly from a phone). Your job is to refine it
into a GitHub issue that a **different agent, with no access to this conversation**, can
implement cold. The issue is the entire handoff: if a fact lives only in this chat, it's lost.

This skill files issues; it never implements them. Implementation happens later when the
maintainer says "implement issue X".

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
   and CLAUDE.md constraints. Search existing issues for duplicates/overlap
   (`gh issue list --search "..." --state all`). Never ask the maintainer something the repo
   already answers — informed questions are the whole value of the interview.
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
  Decisions table. The same rule applies to the Step 5 file-it gate — never file an issue on a
  failed/absent gate; retry, then fall back to a plain-text confirmation. Defaulting is only
  for decisions with a conventional answer, never a substitute for an interview the tooling
  failed to deliver.
- At most **2 rounds**, ≤4 questions each. If more than ~6 decisions are genuinely open, the
  request is underbaked — say which decisions you defaulted and let the preview catch wrong calls.
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

## Step 5 — Render the EDICT, then gate

Every draft becomes an **EDICT** (Executive Decision, Interviewed & Captured for Triage) —
a numbered, permanent record of what was decided, archived in the Claude project folder,
**never committed to the repo** (see plumbing for the path). The maintainer reviews the
rendered EDICT, not chat text: the `AskUserQuestion` modal can hide everything printed
before it, so a draft that exists only in chat is a draft the maintainer never saw.

1. **Number it — from the global registry, not the local folder.** The local edicts folder is
   invisible to parallel sessions (especially remote Claude Code on the web), so numbering from
   it alone collides — three EDICTs once all became `0004`. Compute `NNNN` as `max + 1` (zero-
   padded 4) across **both** shared, cross-session sources:
   - **Published artifacts** — call the Artifact tool with `action: "list"` and scan titles for
     `EDICT-NNNN`.
   - **Filed issues** — scan issue bodies for the `<!-- edict:NNNN ... -->` marker (step 6):
     `gh issue list --search "edict:" --state all` (or the search API), reading the marker.

   Re-run this check **immediately before publishing the html and again immediately before
   filing**; if the number was taken since, bump. The series stays independent of issue numbers
   (like ADRs), but the filed **issue number is the atomic tiebreaker**: if two sessions still
   race to the same EDICT number, their distinct issue numbers disambiguate — so always record
   the `EDICT-NNNN ↔ #issue` pairing (step 6). A residual same-second race can't be fully
   eliminated without a lock the environment doesn't provide; the issue-number anchor is the
   backstop. If you discover an existing collision, keep the earliest-filed EDICT at the lower
   number and renumber the later one(s), noting the correction on the affected issues.
2. **Write `EDICT-NNNN-<slug>.md`** in the edicts folder: a status header (Status: Draft,
   Date, Labels, Artifact: pending) followed by the full issue body.
3. **Build `EDICT-NNNN-<slug>.html`** beside it and publish with the Artifact tool —
   favicon `📜` (stable for the whole EDICT series), title `EDICT-NNNN — <short title>`.
   Load the `artifact-design` skill before writing the page. Branding is pymediate's
   midnight-signal system — copy the token set and header structure from the newest existing
   EDICT html in the folder rather than reinventing it (light: violet primary on
   near-white; dark: cyan primary on near-black indigo; cyan→violet gradient used sparingly;
   both themes via tokens + `data-theme` overrides).
4. **Post the artifact link in chat**, then gate with one `AskUserQuestion`:
   **File it (Recommended)** / **Revise** (say what; edit md + html, republish the same file
   path so the URL is stable, gate again) / **Park it** (set the md Status to Parked; keep
   the EDICT and artifact). Never file without this gate.

## Step 6 — File and board

Create the issue, apply labels, add to the board, set status (see plumbing).

**The filed issue body must carry the artifact link and a machine marker** — this is not
optional, and it's what makes step-5 numbering clash-proof over time. Include, at the bottom of
the body:

- a human footer, e.g. *Captured via the `/edict` skill as **EDICT-NNNN** — [rendered decision
  record & spec](<artifact-url>). Implements [ADR NNNN](...)* (drop the ADR clause if none); and
- a hidden marker: `<!-- edict:NNNN artifact:<artifact-url> adr:<n or omit> -->`.

If the issue was already created without them, add the footer + marker as a **comment** instead
(and backfill the same on any older edict-created issue that lacks it — find them by cross-
referencing the artifact registry against the issues).

Then close out the EDICT: set its md Status to `Filed as <owner/repo>#NN` with the issue URL,
record the artifact URL, and republish the html with the filed status so the archived document
and the issue of record point at each other. Reply with the issue URL, the artifact URL, and a
one-line restatement of what was captured.

## Epic edicts — linking a family of issues

Some requests are one outcome; some are a *program* of many independently-implementable
outcomes (a roadmap, a curriculum, a migration touching N sites). Step 2 already says to split
those — this is how to split them **and keep them connected**, so each child is a cold-start
issue while the whole still reads as one plan.

- **File an epic edict + one child edict per outcome.** Each gets its own `EDICT-NNNN` (the
  series is shared — number them in sequence) and its own GitHub issue.
- **The epic issue is the tracker.** Its body carries the shared context — the philosophy, the
  scheme, the tiered sequence — and a **checklist that links out to every child** (`- [ ] NNN
  <name> — #<issue>`). Label it `roadmap`. It does *not* restate each child's spec.
- **Each child issue is fully self-contained.** A cold agent implements it from the child alone
  (Step 4 template in full). The child links back to the epic in its `## Pointers`
  ("Part of the <epic> roadmap, #<epic-issue>"); the epic never holds the child's only copy of a
  fact. Duplicate the *minimum* shared context each child needs (don't make children read the
  epic to be implementable) — self-sufficiency wins over DRY here.
- **Link them natively.** Attach each child as a **GitHub sub-issue of the epic**
  (`mcp__github__sub_issue_write`, or `gh` where available) so the parent/child tree is real,
  not just prose. Board every issue (epic + children) the same way (Todo).
- **Gate at scale.** Rendering and gating an HTML artifact for *every* child (Step 5) doesn't
  scale past a handful. Publish the **epic artifact + two or three representative child
  artifacts**, gate once on those, and — with the maintainer's approval at that gate — **batch-file
  the remaining children** without an artifact each. The filed issues are the durable record;
  the EDICT `.md` files still get archived for all of them.

---

## Repo plumbing — pymediate (swap this section when porting the skill to another repo)

- **EDICT archive:**
  `/Users/saleyaasin/.claude/projects/-Users-saleyaasin-Development-pymediate/edicts/` —
  outside the repo on purpose; never commit EDICTs. EDICT-0001–0003 (2026-07-10) are the
  founding examples; EDICT-0003's html is the branding reference.
- **Titles are plain descriptive sentences** — Conventional Commits applies to PR titles,
  not issues.
- **Labels:** `roadmap` for feature/process work; `bug`, `documentation`, `process` where
  they fit better.
- **Board:** user-level project **#2 "pymediate"** —
  `gh project item-add 2 --owner sina-al --url <issue-url>`, then set Status = `Todo`:
  project ID `PVT_kwHOAafBSs4Bc38l`, Status field `PVTSSF_lAHOAafBSs4Bc38lzhXdlCo`,
  Todo option `f75ad846` (if `item-edit` rejects these cached IDs, re-look them up with
  `gh project field-list 2 --owner sina-al --format json`). Leave Priority unset unless told.
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
