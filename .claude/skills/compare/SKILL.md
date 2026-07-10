---
name: compare
description: Refresh PyMediate's library-comparison page (docs/content/docs/comparison.mdx) and its anonymized knowledge base (.claude/context/mediator-survey.md) — re-check roadmap issues, optionally re-survey competitor source and re-run the benchmark. Use when asked to update the comparison, after a release, or when a roadmap item (event publishing, streaming, ...) ships.
---

# /compare — refresh the library comparison

The comparison page exists to answer an evaluator's two questions — "why not an
alternative?" and "what does `send()` cost?" — with evidence, and it rots in three ways:
a PyMediate roadmap gap closes, the competitor landscape shifts, or the quoted benchmark
falls behind the current release. This skill checks all three and updates the page and
the knowledge base **together, in the same commit** — they must never disagree.

## Files

- `.claude/context/mediator-survey.md` — the knowledge base. Read it first; it is the
  single source of truth for every claim on the page. Obey its anonymity warning: no
  library names, URLs, star/download counts, or identifying hints ever get written to
  it, the docs page, commit messages, or any other repo file.
- `docs/content/docs/comparison.mdx` — the page. Stays **last** in the sidebar
  (`docs/content/docs/meta.json`) — it serves evaluators arriving from the README or
  home page, not the learning path.
- `scripts/benchmark.py` — the benchmark (PEP 723; also served at the site root as
  `/benchmark.py` by the docs site's build script). `pymediate` stays unpinned there by
  design — don't "fix" that.
- Secondary surfaces that repeat comparison claims and must not go stale:
  `docs/content/docs/index.mdx` ("Why PyMediate?"), `docs/app/(home)/page.tsx`
  (hero + feature grid), `README.md` (Features section link).

## Steps

1. **Read the knowledge base**, note the last-survey and last-benchmark dates.

2. **Sync the roadmap.** `gh issue list --label roadmap --state all --limit 50`, then
   check each issue in the knowledge base's roadmap table. For any closed item, verify
   the capability actually shipped (check `.claude/context/api-signatures.md` /
   `src/pymediate/`), then flip the page row from "Not yet — planned in issue #N" to a
   factual description of what shipped (note whether it's typed — that's PyMediate's
   differentiator), and update the aggregate-findings row. Add rows for shipped
   capabilities the page doesn't cover yet, but only with surveyed data for the
   alternatives column — never guess what competitors do.

3. **Decide whether a re-survey is due**: the last full survey is older than ~6 months,
   the user asked for one, or a claim is in doubt. If so: re-derive the six most popular
   mediator libraries by GitHub stars + PyPI downloads via fresh web search (the
   criterion is objective — identities are re-derivable, which is why they don't need to
   live in the repo), read their **source** (dispatch code, registries, type signatures
   — not READMEs), and update the aggregate findings and per-library profiles
   (codenames Library A–F). Write/update the codename → identity mapping in the
   maintainer's **private Claude memory**, never the repo. Aggregate counts ("five of
   six") must be recomputed, not assumed stable.

4. **Refresh the benchmark if quoting anew** — after a release, a dispatch-path change,
   or if results are stale: `uv run poe benchmark` (full defaults) on the maintainer's
   machine, then update the page's table, the hardware/Python/pymediate-version caveat
   sentence, and the knowledge base's results section. Never edit quoted figures without
   a fresh run, and never benchmark against named competitors — only against the direct
   call (see the script's docstring for why).

5. **Update the page.** Hard-won rules from the page's history:
   - Aggregate phrasing only — no names, and no traits that identify ("the heaviest"
     was removed for this exact reason; "one of the six" is the pattern).
   - Describe approaches, never projects or maintainers; keep rows that favor the
     alternatives and the "a mediator is the wrong tool for hot paths" paragraph —
     the page's credibility is its value.
   - Apply the `ms-style-docs` skill mechanics: second person, no colon before code
     blocks/tables, spell out numbers zero–nine in prose, no bold-for-emphasis,
     descriptive link text. One deliberate deviation: this doc set uses **spaced**
     em dashes — keep the project convention.
   - The read-before-running warning stays a `<Callout type="warn">` above the
     `uv run https://pymediate.sina-al.uk/benchmark.py` block.

6. **Update the knowledge base in the same edit session** — survey date, findings,
   roadmap table, benchmark results — then sweep the secondary surfaces (index.mdx,
   home page, README) for claims the changes invalidated.

7. **Verify and ship**: `cd docs && pnpm types:check && pnpm build` (plus
   `uv run poe lint` if the script changed). Commit page + knowledge base together
   (`docs: ...`); push per the repo's lane-1 default. Confirm the Documentation
   workflow's **Deploy documentation** job ran (not skipped) and spot-check the live
   page.
