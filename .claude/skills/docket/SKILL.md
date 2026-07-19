---
name: docket
description: Read all the maintainer's open, implementation-ready issues and recommend the single best one to pick up next — weighing how they interact, what unblocks what, and what matters most — then present that verdict plus ranked runners-up. Advisory and read-only; changes nothing on GitHub. Use when the maintainer asks "what should I work on next", "what's next", "pick my next issue", "what's on the docket", or wants to spend a soon-to-expire strong-model allowance well.
---

# /docket — open edicts → the one to do next

`edict` is the *in*: an idea becomes a filed, implementation-ready GitHub issue. `docket` is the
*out*: all the pending issues become **one recommendation** for what to pick up next. The
maintainer implements serially, one at a time, applying their own judgment — this skill informs
that judgment, it does not replace it.

**Advisory and read-only.** The docket reads issues and reasons out loud. It never writes to
GitHub, never touches labels, never sets a board field, never opens or assigns anything. The
maintainer acts on the verdict by saying "implement issue X" — the decision, and the doing, stay
theirs. If asked to *persist* a pick (label it, rank the board), say that's out of scope for the
docket and point at doing it by hand.

Two principles this skill is built on:

- **Recommend one, show your work.** A serial worker needs a single answer, not a plan. But the
  answer is only trustworthy if the reasoning is visible — so name one pick, then show the ranked
  runners-up with one-line reasons, so the maintainer can override a call they disagree with.
- **Sequence beats priority.** The most "important" issue is the wrong pick if something else must
  come first, or if doing it now collides with a sibling, or if it's blocked. Readiness and
  interaction usually decide the next step; raw importance breaks ties.

## Step 1 — Gather the candidates

Pull every **open** issue (GitHub MCP `list_issues` / `search_issues`, or `gh issue list --state
open` where the CLI exists). `list_issues` output can be large — fetch titles, numbers, labels,
and bodies, and if the payload is unwieldy, extract fields rather than reading it whole.

For the issues that survive Step 2's eligibility filter, read the **full body** — the Summary,
Constraints & non-goals, Pointers, and Acceptance criteria are where interaction and readiness
actually live. Also read sub-issue links and parents (`issue_read` `get_sub_issues` /
`get_parent`) — the parent/child tree is a first-class dependency signal.

## Step 2 — Filter to what's eligible

An issue is a candidate for "next" only if it's genuinely pickable. Exclude, and say briefly why:

- **Draft.** A `draft`-labeled issue is still in `edict`'s review loop — a proposal, not committed
  work. Never recommend one. Mention it exists ("2 drafts still in review") but keep it out of the
  ranking.
- **Already in flight.** An issue with an assignee, a linked open PR, or an obvious in-progress
  branch (`claude/issue-*`) is being worked — skip it. "What's *next*" means not-yet-started.
- **Blocked.** If the body, a Pointers "depends on / blocked by", or an unchecked prerequisite
  sub-issue says something else must land first, it isn't eligible *yet* — surface it as blocked
  and name its blocker (which is often the real answer).
- **Underbaked.** An issue with no testable acceptance criteria or an open "investigate, may
  reject" framing isn't implementation-ready. It can still be the pick if the *next* step is a
  decision rather than code — but call that out; don't hand a cold implementing agent a wish.

Epics (label `roadmap` with a child checklist / GitHub sub-issues) are usually **not** the unit of
work — their children are. Rank the ready child, not the epic; note the epic for context.

## Step 3 — Build the interaction picture

Before ranking, sketch how the eligible issues relate — this is the whole reason a serial worker
needs help. For each, note:

- **Unblocks / is unblocked by** — does finishing this free up others? Foundational work that
  several edicts build on earns its place first. An issue whose blocker is still open drops out
  (Step 2).
- **Collides with** — do two issues rewrite the same surface? Doing one reshapes the other; pick
  the one that sets the shape, and flag that the sibling should be re-read afterward, not done in
  parallel.
- **Composes with** — issues that share context are cheaper back-to-back. Worth a one-line "and #N
  is a natural follow-on" note, without turning the verdict into a batch.

## Step 4 — Weigh and pick

With eligibility and interaction settled, order the candidates. Criteria, roughly in the order they
usually decide it:

1. **Readiness & sequencing** — ready now, nothing waiting on a blocker, and ideally unblocks
   others. A foundational issue that clears the path for three more beats a bigger isolated one.
2. **Interaction safety** — picking it now doesn't strand or conflict with a sibling; if anything,
   it sets the shape the siblings need.
3. **Importance / impact** — user-facing value, a real bug fixed, a correctness gap closed, or a
   roadmap milestone reached. This breaks ties between similarly-ready issues.
4. **API-surface & judgment weight** — issues touching `__all__`, `RequestHandler`, or
   `ServiceProvider` (ADR-likely, per CLAUDE.md) demand exactly the maintainer judgment that can't
   be delegated. These are strong picks *when the maintainer is engaged and has the bandwidth* —
   and poor picks for a tired end-of-day slot.
5. **Effort / fit** — a serial worker doing one at a time cares about size. Fold in any focus the
   maintainer gave (Step 5).

This is judgment, not a formula — don't compute a score. On a genuine tie, present the close call
and let the maintainer break it; that's the serial judgment the skill exists to serve, not to
pre-empt.

## Step 5 — Focus modes (optional)

The default is a cold read of what's next. The maintainer may steer with a focus — honor it as a
strong filter/re-weight, not an override of hard blockers (a blocked issue stays blocked):

- **Area / theme** — "docs today", "something in the sync mirror", "a quick win". Rank within that
  slice; if it's empty, say so and offer the unfiltered pick.
- **Appetite** — "small", "something meaty". Re-weight by effort.
- **Allowance burn** *(recognize this one explicitly)* — the maintainer has strong-model allowance
  about to expire and wants to spend it where it pays off most. They'll say something like "I've
  got Opus allowance about to reset, what should I burn it on" (optionally with a rough time or
  quantity budget). Invert the usual effort preference and rank by **how much the work rewards a
  strong model**:
  - **Favor** the reasoning-dense, hard-to-get-right issues: generics / type-system work and the
    typing-snippet corpus, ADR-worthy API design, subtle correctness, anything touching the
    async/sync mirror where a missed parity implication bites later. This is the work where model
    strength changes the outcome.
  - **Deprioritize** work a weaker model or a later session handles fine at lower cost: docs
    wording, example READMEs, mechanical refactors, dependency bumps, tooling glue. Not "never" —
    just not what you burn scarce strong-model time on.
  - If a budget was given, prefer a pick (or a foundational-first pair) that plausibly *fits and
    finishes* in it — an unfinished thorny change stranded at reset is worse than a smaller one
    completed. Say how the budget shaped the call.

## Step 6 — Deliver the verdict

Advisory output, in chat. No GitHub writes. Shape:

- **The pick** — issue number, title, link, and a 2–4 sentence rationale grounded in Step 4:
  why *this* one now, what it unblocks or de-risks, and (if a focus applied) how the focus shaped
  it. If the real next step is a decision rather than code (an "investigate/may reject" issue, an
  ADR call), say that plainly.
- **Runners-up** — a compact ranked list of the other eligible issues, each with a one-line
  why-not-yet ("#N — blocked on #M", "bigger and isolated; nothing waits on it", "collides with
  the pick, do it after"). This is where the sequencing logic shows.
- **Set aside** — one line for what was excluded and why (drafts in review, in-flight, blocked),
  so the maintainer sees the docket didn't just forget them.
- **Close** — remind that it's their call: "Say *implement issue N* to start, or tell me to
  re-rank with a focus." Then stop — no board edits, no labels, no PR.

Edge cases: **nothing eligible** (all drafts / all in flight / all blocked) — say so and name the
nearest unblock. **One eligible** — name it, still note what's set aside. **All blocked on one
thing** — that blocker is the verdict.

---

## Repo plumbing — pymediate (swap this section when porting the skill to another repo)

- **Source of truth:** open issues on `sina-al/pymediate`. Read-only; the docket never writes.
- **Labels that matter here:**
  - `draft` — still in `edict`'s review loop; **never recommend**, mention as set-aside.
  - `roadmap` — feature/process work; the bulk of the candidate pool. Epics carry a child checklist
    and GitHub sub-issues — rank the ready *child*, not the epic (e.g. the "Pedagogical examples
    curriculum" epic vs. its per-example children).
  - `process`, `bug`, `documentation` — used as they fit; `bug` usually earns an importance bump.
- **Board:** user-level project **#2 "pymediate"** (<https://github.com/users/sina-al/projects/2>).
  Its Priority field is generally unset and the docket does **not** set it — advisory only. You may
  *read* board state for context, but the verdict lives in chat.
- **Dependency signals to read for:** Pointers "Part of the <epic> roadmap, #<n>" links, GitHub
  sub-issue parent/child trees, and prose prerequisites in Summary / Constraints. Real examples of
  the shapes to expect: an issue that waits on another ("once ordering leaves the protocol" — do
  the ordering issue first), and a curriculum epic whose example children are the actual units.
- **Judgment-weight surfaces (CLAUDE.md "Quality bar"):** changes to `__all__` in `__init__.py`,
  the `RequestHandler` class, or the `ServiceProvider` protocol are ADR-likely and breaking-change
  candidates — the maintainer-judgment work that suits an engaged slot and the allowance-burn mode.
- **Repo rules that shape "rewards a strong model" (allowance-burn):** the generics design and the
  typing-snippet cross-checker (`tests/typing/snippets/`), the async/sync mirror parity
  (`tests/test_parity.py`), and ADR-worthy API shape are the high-leverage end; docs/MDX mirroring,
  `examples/` (post-release, via the `example` skill), and tooling bumps are the low-leverage end.
