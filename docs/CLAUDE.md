# docs/ — the documentation site

Next.js + Fumadocs app, pnpm, Node 22, **static export** (`docs/out/`), deployed to GitHub
Pages at <https://pymediate.sina-al.uk> from `main` via `docs.yml`. The project `CLAUDE.md` (at `.claude/CLAUDE.md`)
holds the always-loaded summary; this file is the working detail for sessions touching
`docs/`.

## Tasks

Use the `poe` tasks from the repo root — they mirror what `docs.yml` runs in CI:

- `uv run poe docs:install` — once, before anything else (`pnpm install --frozen-lockfile`).
- `uv run poe docs:serve` — dev server with live reload.
- `uv run poe docs:check` — lint + type-check; run before committing docs changes.
- `uv run poe docs:build` — static build into `docs/out/`; `docs:clean` removes outputs.

`docs.yml` invokes pnpm directly rather than through poe (Node-only job — see the
"poe tasks vs. inline workflow steps" carve-out in the project CLAUDE.md); keep the workflow
steps and the poe tasks in sync.

## Content layout

MDX under `docs/content/`:

- `docs/` — the site's Docs section. Sidebar order lives in `meta.json`:
  getting-started → guide → api → comparison. The introduction teaches the core request flow;
  guides cover user tasks; the API section is reference material. Runnable projects are maintained
  in the repository's `examples/` curriculum rather than repeated as a separate site section. New
  pages must be added to `meta.json` or they won't appear in the sidebar.
- `docs/api/*.mdx` — the API reference, **hand-written** to mirror the source docstrings
  in `src/pymediate/`. A change to a public docstring or signature needs the matching
  page updated, and vice versa. Sync and async pages mirror each other the same way the
  code does.
- `docs/comparison.mdx` — maintained by the `compare` skill only; its knowledge base
  (`.claude/context/mediator-survey.md`) must never contain competitor names.
- `articles/` — long-form essays with byline frontmatter. These are the maintainer's
  voice: don't draft or edit article prose without an explicit request, and interview
  before ghost-writing.

Everything else under `docs/` (app/, components/, config) is app code — TypeScript,
checked by `docs:check`.

## Conventions

- **Every runnable or standalone code example must actually run** — same bar as docstrings (the
  project CLAUDE.md, "Docstrings"): verify it in a scratch shell before committing. A focused
  fragment may rely on definitions shown earlier on the page or application-specific symbols that
  the surrounding text identifies. Add `(excerpt)` to its title when those omissions are not clear
  from the immediate context.
- The site brand is the "midnight-signal" token system (light: violet primary on
  near-white; dark: cyan primary on near-black indigo; cyan→violet gradient used
  sparingly). Reuse existing tokens/components rather than introducing new colors.
- `docs/adr/` is deliberately outside `content/` — never move ADRs into the published
  site, never link them from site pages as if they were docs.
- No changelog page — the GitHub Release notes are the canonical changelog (see
  OPERATIONS.md, "Release notes"); don't add a second source.
