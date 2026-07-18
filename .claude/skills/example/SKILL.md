---
name: example
description: Create or update an example project in examples/ to this repo's full bar — structure, README quality, IDE polish (no squiggles), Codespaces devcontainer, gallery entry, and release-runner verification. Use whenever adding a new example, restructuring one, or editing an example's README, even if the request only mentions part of that (e.g. "add an example for X" or "clean up this example").
---

# /example — build or update an example

## Why examples get extra care

Examples are a conversion point, not an appendix. An impatient visitor often lands on
`examples/` **without having read any documentation** — the example README is their first
and possibly only impression, and research on developer onboarding is blunt about what
happens next: if the first screen doesn't answer *what is this / why should I care / how
do I run it* within ~10 seconds, they leave; developers who reach a working result within
minutes convert at 3–4× the rate of those who don't. So every example must be
self-contained, gentle, and runnable by copy-paste. When in doubt, cut.

## Pedagogy — write for adoption

The whole `examples/` set is a **curriculum**, and every README and code comment is written
with one goal: **adoption**. Not by selling — by *teaching*. Internalize these:

- **Write for the reader who came looking for *their* use case.** Someone lands on an example
  because they have a specific question ("how do I stream a response?", "where does auth go?").
  The example must answer *exactly that question* — the questions that reader actually has, no
  more, no less. It is not a brochure; it's the answer they searched for.
- **No example needs to sell the package.** Drop the pitch. An example earns adoption by being
  the thing that unblocks the reader. Trust the curriculum as a whole to make the broader case.
- **Each example is an exposition — the story of a problem pymediate solves.** Start from the
  *fundamental problem* (the pain a developer feels without the library), then reveal how
  pymediate resolves it. The README tells that story; the code comments serve the same story,
  narrating the *why* at the point it becomes concrete, not restating the *what*.
- **One primary revelation per example.** Every example anchors exactly one insight. If it needs
  two, it's two examples. This is what makes the set a curriculum instead of a pile.
- **Two example flavors, both valid:**
  - *Revelation* — show the good pattern for one capability, cleanly (`send`, `publish`, `stream`).
  - *Objection-answering contrast* — take a real doubt ("why not one big service?", "why not a
    decorator?", "where does validation even go?"), **build the naive approach, show it failing
    concretely**, then show the pymediate approach succeeding at the identical task. A contrast
    example's single revelation *is* the comparison, so its before→after shape is the teaching
    device — not a violation of the one-revelation rule.

## The contract (mechanical requirements)

`examples/README.md` § "The examples contract" is authoritative. Summary: standalone uv
project, committed `uv.lock`, `pymediate>=0.5` loose bound (extras like `pymediate[di]`
are fine — the release runner's re-pin preserves them), tests in the default `dev` group
so `uv sync && uv run pytest` is the whole contract, **never** define `[tool.uv.sources]`
or `[[tool.uv.index]]`, and a README. `release.yml` discovers `examples/*/pyproject.toml`
dynamically — no pipeline wiring per example.

Other repo gotchas: handler classes register in a process-global registry at import time
(fine within one example; never import another example's modules), and use `httpx2`, not
classic `httpx`, for HTTP test clients (starlette deprecated httpx there).

## Structure: flat or src — decide by module count

- **One source module** → flat: `app.py` + `test_app.py` at the root, `[tool.uv]
  package = false`. Template: `examples/basic/`. Folder ceremony makes tiny examples
  read worse, not better.
- **More than one source module** → src layout, installed as a real package:

  ```
  <example>/
  ├── README.md
  ├── pyproject.toml        # package = true (default), hatchling, [project.scripts]
  ├── pyrightconfig.json
  ├── .vscode/settings.json
  ├── src/<package>/        # short domain noun (e.g. taskboard), NOT the example name
  │   ├── core.py
  │   └── adapters/…        # or whatever grouping fits
  └── tests/
  ```

  Template: `examples/090-adapters/`. Being a real package is what buys pleasant
  commands: `uv run taskboard …` via `[project.scripts]`,
  `uv run uvicorn taskboard.adapters.fastapi:app` — never
  `uv run python src/….py` paths in a README. uv installs the project editable on sync,
  which also makes IDE imports resolve.

Directory names are kebab-case and content-descriptive. Async is the default and goes
**unmarked** (`<name>`); its synchronous mirror is `<name>-sync` and must mirror it
structurally (same rule as the library: async is the top-level API, sync the mirror — the
async default leads in reading order). A topic example that isn't part of an async/sync
pair keeps a plain descriptive name (e.g. `with-dependency-injector`, which happens to be
built on the sync API but sits off the async/sync axis).

## The README — treat it as a landing page

Every section below the first screen is optional; the first screen is not. Rules distilled
from onboarding research (10-second test, time-to-first-success < 5 min, show-don't-tell,
progressive disclosure):

1. **First screen**: title, Codespaces badge, then 1–2 sentences of *what this shows and
   why it's interesting*, then the run block. No history, no architecture lecture, no
   prerequisites beyond `uv`.
2. **Run block ≤ 3 copy-paste commands**, starting with `uv sync`. It must work verbatim
   from the example directory on a fresh clone.
3. **Show every expected output.** After each command or curl, show what the user should
   see (trimmed to the interesting lines). A reader must be able to "run" the example in
   their head without executing anything.
4. **One money-shot snippet** early: the ~10 lines that carry the example's point (e.g. a
   typed request + `mediator.send`), followed by 2–4 short sentences of explanation.
   Plain words; name concepts only when the snippet makes them concrete.
5. **File tour**: one line per file, in suggested reading order, with a "start with X"
   pointer. Tables or tight bullet lists, not prose paragraphs.
6. **Progressive disclosure, max two heading levels.** Paragraphs of 2–3 sentences.
   Details (design notes, error-mapping tables, caveats) go below the fold; links to the
   docs site and the next example go last, under "Where next".
7. **Tone**: friendly and direct. No jargon before it's earned, no "simply", no wall of
   badges. End with an invitation (try the next example, open the docs), not a dump.

## IDE polish — a fresh `uv sync` must mean zero squiggles

Each example ships its own editor config so it's pleasant standalone *and* inside the
monorepo (the repo-root `ruff.toml` enforces docstring rules examples shouldn't inherit):

- `pyrightconfig.json`: `{"typeCheckingMode": "standard", "venvPath": ".", "venv":
  ".venv"}` — `standard` matters: basedpyright defaults to `recommended`, whose nitpick
  warnings (`reportUnusedCallResult`, …) would show as squiggles in example code.
  Squiggles from unresolved imports are legitimate only before the venv exists.
- `.vscode/settings.json`: `python.defaultInterpreterPath` → `.venv/bin/python`.
- `[tool.ruff]` in the example's `pyproject.toml`: line-length 100, `E,W,F,I,B,C4,UP`
  (no `D` — READMEs carry the explanation), double quotes. This shadows the repo config.
- Verify by running `uv run ruff check .` and basedpyright (or checking the IDE) inside
  the example after `uv sync`.

## Codespaces devcontainer

Each example gets `.devcontainer/<example>/devcontainer.json` at the **repo root**
(Codespaces only discovers them there): python 3.12 base image + uv feature +
`postCreateCommand` that syncs the example, interpreter default pointed at the example's
venv. Copy an existing one and adjust the three obvious fields. README badge:

```markdown
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F<example>%2Fdevcontainer.json)
```

## Gallery entry

`examples/README.md` opens with the gallery. Add/update the new example's card: name
(linked), one-sentence hook, "start here"-ordering position. Keep the recommended reading
order coherent: basic → basic-sync → events → with-dependency-injector →
adapters → adapters-sync → (new ones slotted deliberately, not appended blindly).

## Verification bar (all of it, every time)

1. `uv sync && uv run pytest` green inside the example.
2. **Every README command run by hand**, including expected outputs shown in the README
   (update them if they drift), error paths, and CLI exit codes; servers actually started
   and curled.
3. `uv run ruff check .` clean inside the example; no IDE squiggles post-sync.
4. From the repo root, `scripts/run_examples.py` passes **all** examples in both modes:
   `--version <latest-on-PyPI> --index https://pypi.org/simple/` and
   `uv build && … --wheel dist/pymediate-*.whl`.
5. Docstrings/code style match the library's (the repo formatter hook handles format).

Commit as `feat(examples): …` / `fix(examples): …` / `docs(examples): …` — patch-bump
territory (no package changes).
