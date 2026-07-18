---
name: example
description: Create or update a project in examples/, including its structure, README, editor settings, Codespaces devcontainer, gallery entry, and release-runner checks. Use whenever adding or restructuring an example, or editing an example README.
---

# /example: create or update an example

## Purpose

The `examples/` directory is a guided learning path. A reader may open an example without
reading the documentation first, so each project must explain its prerequisite knowledge,
teach one main idea, run from copied commands, and point to the next relevant example.

Examples also act as downstream release tests. They install PyMediate as a dependency and
exercise its public API against wheels and published packages. Readability and release
verification are requirements of the same project, not separate concerns.

## Teaching model

- **Follow the curriculum order.** Introduce a term before relying on it. Link back to the
  prerequisite example when the current topic assumes an earlier concept.
- **Teach one main idea per example.** Supporting details are allowed only when they help
  explain or verify that idea. Split unrelated lessons into separate examples.
- **State the problem directly.** Explain the limitation, show the relevant code, then
  explain the result. Do not dramatize the limitation or promote the package.
- **Use fair comparisons.** A contrast example may implement a reasonable alternative and
  show where its trade-off appears. Do not weaken the alternative to make PyMediate look
  better.
- **Keep async and sync as parallel tracks.** The unmarked directory is the async default;
  `<name>-sync` is its structural mirror. Each README must teach the complete lesson to a
  reader following only that track. Avoid duplicating incidental detail, but do not send a
  sync reader to the async README for the rationale or code-reading route.
- **Make comments explain decisions.** Code comments should explain why a boundary or call
  exists. Do not restate the next line of code.

## Release contract

`examples/README.md` under "The examples contract" is authoritative. In summary, each
example is a standalone uv project with a committed `uv.lock`, a README, and a direct
PyMediate dependency with a loose lower bound. Extras such as `pymediate[di]` are allowed.
Pytest belongs to the default `dev` dependency group so these commands are sufficient:

```bash
uv sync
uv run pytest
```

The release runner owns the PyMediate source and index while testing a candidate. Do not
check in `[[tool.uv.index]]`. `[tool.uv.sources]` may contain `{ workspace = true }` entries
for packages inside a multi-package example. The complete architecture example has one
documented repository-checkout override; the runner validates and removes it before
re-pinning PyMediate. No other PyMediate source override is allowed.

Set the lower bound to the earliest known PyMediate release that provides every API used by
the project. This is a maintainer-reviewed compatibility claim: the contract check validates
its form, while candidate wheel and latest-PyPI runs do not prove older releases still work.

Handler classes register in a process-global registry when their class body executes. Do
not import modules from another example, and do not redefine handlers for the same request
type in separate tests. Use `httpx2`, not classic `httpx`, for Starlette HTTP test clients.

## Names and curriculum order

Every top-level directory uses `NNN-topic-name`, with a three-digit curriculum position and
a kebab-case topic. Leave gaps between positions so a prerequisite can be inserted later.
An async/sync pair shares one number:

```text
040-pipeline-behaviors/
040-pipeline-behaviors-sync/
```

The async project is listed first. Reserve `900-` for the complete application at the end
of the curriculum so later focused topics can be inserted without renumbering it.

## Project structure

Use a flat project when there is one source module:

```text
<example>/
├── README.md
├── app.py
├── test_app.py
├── pyproject.toml       # [tool.uv] package = false
├── pyrightconfig.json
└── .vscode/
```

Use an installed `src` package when there is more than one source module:

```text
<example>/
├── README.md
├── pyproject.toml       # hatchling and any [project.scripts]
├── pyrightconfig.json
├── .vscode/
├── src/<domain-name>/   # short domain noun, not the example directory name
└── tests/
```

Use `examples/010-basic/` as the flat reference and `examples/090-adapters/` as the
multi-module reference. Installed projects expose useful commands such as
`uv run taskboard` or `uv run uvicorn taskboard.adapters.fastapi:app`; READMEs must not
require `python src/...` paths.

## README order

Use this order unless the example has a concrete reason to omit an optional section:

1. **Title and Codespaces badge.** Use the directory name as the title.
2. **Opening.** In one or two short paragraphs, state what the example teaches, what prior
   example it assumes, and why the distinction matters. Lead with the point, not a
   rhetorical question.
3. **`## Run`.** State that commands run from the example directory. The first command block
   has at most three copyable commands, starts with `uv sync`, and works on a fresh clone.
   Keep the repository-root `cd examples/<name>` instruction in the gallery so the same block
   also works when Codespaces opens the example as its workspace.
4. **Expected output.** Show the program or request output immediately after the command that
   produces it. Do not reproduce dependency-install logs. Trim timestamps, platform details,
   and other unstable lines. State when output varies.
5. **Main code excerpt.** Show the smallest excerpt that carries the lesson, then explain it
   in two to four short sentences. Use a descriptive heading, not labels such as "money
   shot" or "the magic."
6. **`## Read the code`.** Use a `File | What to read` table in reading order. Mark one file
   as the starting point and describe each file in one line.
7. **`## Details`**, optional. Put constraints, error behavior, and design qualifications
   here. Use topic-specific headings when they are clearer than a general details section.
8. **`## Where next`.** Link to the next curriculum topic, then the sync or async twin, then
   the relevant prerequisite or documentation. Do not end with an unrelated list of links.

Use no more than two heading levels below the title. Keep paragraphs to one idea and usually
two or three sentences.

## Writing standard

- Use direct, neutral language. Remove sales claims, urgency, praise, and staged reactions.
- Do not use "simple," "obvious," "just," or "magic" to dismiss work the reader may find
  difficult.
- Do not use invented labels, abbreviations, or decorative metaphors. Use established developer
  acronyms such as API, CLI, DTO, HTTP, JSON, and SDK without spelling them out. Define less
  familiar or topic-specific abbreviations on first use.
- Keep established technical terms when they are precise. Explain them before depending on
  them; do not replace them with vaguer wording merely because they are technical.
- Preserve facts, conditions, identifiers, numbers, and commands while editing prose.
- Prefer a literal heading such as "Handler dependencies" over an informal heading such as
  "The sharp edge" or "Small print."

## IDE files

A fresh `uv sync` must leave the example free of editor diagnostics. Each ordinary example
contains:

- `pyrightconfig.json` with `typeCheckingMode: "standard"`, `venvPath: "."`, and
  `venv: ".venv"`;
- `.vscode/settings.json` pointing `python.defaultInterpreterPath` at
  `${workspaceFolder}/.venv/bin/python`, with the shared test, Ruff, and cache exclusions;
- `.vscode/extensions.json` recommending Python, Pylance, and Ruff;
- `[tool.ruff]` settings in `pyproject.toml`: line length 100, rules
  `E,W,F,I,B,C4,UP`, double quotes, and no docstring rules.

The complete architecture example may add YAML support and narrower analysis paths. The
ordinary projects do not install repository-maintenance tools into their environments. Run
Ruff and basedpyright from the repository environment with the example's own configuration.

## Codespaces

Each example has `.devcontainer/<example>/devcontainer.json` at the repository root.
Codespaces only discovers configurations there. Use Python 3.12, install uv, and set
`workspaceFolder` to the selected example directory so its `.vscode` settings apply. Run
`uv sync` after creation, point the interpreter at `${containerWorkspaceFolder}/.venv`, and
include the same Python, type-checker, and Ruff extensions recommended by the project.

Use this badge below the README title:

```markdown
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F<example>%2Fdevcontainer.json)
```

## Gallery

Update `examples/README.md` whenever an example is added, renamed, removed, or changes its
main lesson. Group topics by learning stage, keep rows in numeric order, and present async
and sync links together so a reader can follow one track without stepping through both.
Update `pymediate.code-workspace` and the matching devcontainer at the same time.

## Verification

Complete all checks that apply:

1. In every changed example, run `uv sync` and `uv run pytest`.
2. From the repository root, run `uv run ruff check examples/<name>` and
   `uv run basedpyright --project examples/<name>/pyrightconfig.json` for each changed
   project.
3. Run every README command and compare the actual output and exit status with the text.
   Start and exercise documented servers rather than checking only that they import.
4. From the repository root, run `uv run poe examples:test --check-contract`.
5. Run `uv run poe examples:test --check-repository` to check numbering, project names,
   README sections and links, editor files, devcontainers, and workspace entries.
6. Build the package and run the complete gallery against the
   wheel with `uv run poe examples:test --wheel dist/pymediate-*.whl`.
7. Run the complete gallery against the latest PyPI release with
   `uv run poe examples:test --version <version> --index https://pypi.org/simple/`. If a
   next-release example declares a higher lower bound, record that expected incompatibility;
   do not lower the bound or add a temporary workaround to make an older release pass.
8. Run the repository checks required by any shared files changed, including
   `uv run poe actions:lint` after workflow edits.

When an example starts using a newer API, verify its declared lower bound separately and raise
the bound if needed. Do not infer lower-bound compatibility from a latest-version run.

Use `feat(examples): ...`, `fix(examples): ...`, or `docs(examples): ...` for the commit or
pull-request title. Example-only changes are patch-release work.
