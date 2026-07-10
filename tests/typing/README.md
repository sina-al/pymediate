# Type safety tests

A cross-checker harness that pins down PyMediate's static-typing contract for users of
**mypy** and **pyright/basedpyright** alike. One shared snippet corpus, three verdicts per
snippet: mypy `--strict`, basedpyright `standard` (vanilla pyright parity), and basedpyright
`recommended` (the strictest based defaults).

## Philosophy

These tests focus on compile-time type checking, not runtime behavior. If pymediate's runtime
validation already catches an error, it doesn't need a snippet here.

**What belongs here:**

- Type inference through `mediator.send()`
- Response type correctness
- Type narrowing (Optional, Union)
- Complex nested type handling

**What doesn't belong here:**

- Handler signature validation (runtime validation catches this)
- Request/Handler registration errors (runtime validation catches this)
- Anything testable with regular unit tests

## The contract

Every snippet under `snippets/valid/` must:

- pass `mypy --strict`,
- produce **zero errors and zero warnings** under basedpyright in *both* modes — a based
  user on the strictest defaults gets a spotless experience, and
- **execute successfully at runtime** (`test_snippets_runtime.py`) — "valid" means it
  typechecks *and* runs. Sync snippets run their scenario at module level; async snippets
  define `async def main()` and the harness supplies the event loop.

Every snippet under `snippets/errors/` is **deliberately type-invalid** and must be flagged
by *every* checker, with the specific diagnostic pinned per checker in `expectations.py`
(mypy error codes and pyright rule names don't map 1:1). Never "fix" these files, add
`# type: ignore`, or exclude them from a checker — a diagnostic in `errors/` is the suite
working.

On top of the corpus, `test_basedpyright.py` enforces **100% public-API type completeness**
via `basedpyright --verifytypes pymediate` — no exported symbol may resolve as `Unknown` in
a user's editor.

## Configuration isolation

- `mypy_snippets.ini` — dedicated mypy config passed via `--config-file` so the repo-root
  `mypy.ini`'s `[mypy-tests.*]` suppressions can never leak into the snippets and mask the
  errors they exist to catch. Don't point the harness back at the root config.
- `basedpyright_standard.json` / `basedpyright_recommended.json` — one checked-in config per
  mode; the harness runs each once per session over the whole corpus.
- Checker versions are pinned by `uv.lock`, and `test_basedpyright.py` additionally asserts
  the exact basedpyright version (`PINNED_BASEDPYRIGHT_VERSION`): diagnostics drift across
  releases, so upgrades must be deliberate and reviewed against the corpus.

## Layout

```
tests/typing/
├── test_mypy.py                  # mypy half of the harness (mypy API, per-snippet)
├── test_basedpyright.py          # basedpyright half (both modes) + --verifytypes gate
├── test_snippets_runtime.py      # every valid/ snippet must also run
├── expectations.py               # per-checker expected diagnostics for errors/
├── mypy_snippets.ini             # isolated mypy config for the snippets
├── basedpyright_standard.json    # vanilla-pyright-parity mode config
├── basedpyright_recommended.json # strictest based-mode config
└── snippets/
    ├── valid/                    # must be clean everywhere AND run
    └── errors/                   # must fail every checker, as pinned
```

## Running

```bash
# The whole harness
uv run pytest tests/typing/ -v

# One checker's half
uv run pytest tests/typing/test_mypy.py -v
uv run pytest tests/typing/test_basedpyright.py -v
```

## Adding a snippet

1. Drop the file in `valid/` or `errors/`.
2. For `errors/`, add its expected diagnostics to both tables in `expectations.py`
   (`TestExpectationsCoverCorpus` fails until you do).
3. For `valid/`, keep it warning-free under based `recommended` (use `@override` on handler
   and behavior `__call__` overrides, consume `Services.add(...)` results — chain into
   `.provider()`) and make sure it actually runs.
