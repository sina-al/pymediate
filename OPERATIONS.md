# Operations

How code gets into this repository and how releases get out of it. This is the reference
for the repo's operating model — the rulesets, workflows, and identities below exist to
enforce it mechanically, and anything they enforce is documented here.

## The model in one paragraph

`main` is the trunk and belongs to the maintainer: it moves fast, by direct push or merged
PR, and **it is allowed to be red**. `stable` is the released history: it only ever
receives reviewed, fully-green cuts of main, one merge commit per release, each tagged
`vX.Y.Z`. The version lives in the tag alone (derived at build time by hatch-vcs), the
changelog is generated from conventional commits, and publishing runs on short-lived
credentials end to end. Nothing about a release is hand-assembled, and abandoning a release
at any point before PyPI costs nothing but a version number.

## Contribution lanes

There are exactly three ways code lands on `main`, plus one planned:

| Lane | Who | Path | Gate |
|---|---|---|---|
| 1. Direct push | Maintainer only | push to `main` (ruleset bypass) | none — see "main may be red" |
| 2. External PRs | Anyone, from forks | fork → PR → squash-merge to `main` | required checks + maintainer merge; conventional-commit title enforced |
| 3. Dependency automation | Dependabot | branch → PR → squash-merge | required checks; **patch-level bumps auto-merge** (approve + auto-merge once green), minor/major wait for review |
| 4. *(planned)* Agent lane | Claude Code cloud sessions | PR, reviewed like lane 2 | [#17](https://github.com/sina-al/pymediate/issues/17) |

**No foreign branches on origin.** branch-guard blocks branch creation, update, and
deletion repo-wide for everyone except the maintainer, Dependabot, and the
`pymediate-releaser` App. Contributors work from forks — origin's namespace is reserved.

**main may be red.** Checks run on every push to main (informational), but nothing forces
main to stay green, and a red main is a legitimate state — trunk development shouldn't
stall on a broken test the maintainer plans to fix next. The invariant lives elsewhere:
**a release cannot contain a red main**, because the release PR re-runs every required
check on the exact tree being released, and `stable`'s ruleset will not merge without them.

## The release lifecycle

```
                    gh workflow run prepare-release.yml -f bump=auto|patch|minor
                                        │ (maintainer-only: dispatch needs write access)
                                        ▼
        next version computed from the last tag  ──  burned versions skipped
        cut branch release/vX.Y.Z pushed at main HEAD  (zero commits of its own)
                                        │
                                        ▼
              PR: release/vX.Y.Z → stable        "chore(release): vX.Y.Z"
              ├── the DIFF is everything since the last release — reviewing it
              │   reviews the release (this is the only review lane-1 pushes get)
              ├── body: bump rationale, full changelog, API impact report
              ├── comments: per-Python test results, coverage, pip-audit,
              │   dependency review, API breaking-change report vs last release
              └── required checks (the green gate): Checks, Test Suite,
                  Documentation, All Checks Passed, Release Test Results, Examples
                  (every example against a wheel built from the cut), CodeQL
                                        │
              close PR ──► cut branch auto-deleted; zero consequence; done
                                        │
                            merge (merge commit, human approval #1)
                                        ▼
              tag-release.yml tags the merge commit vX.Y.Z  →  starts release.yml:
              validate → build (+ provenance attestation) → install matrix
                → examples against the built wheel → TestPyPI
                → examples against TestPyPI
                → pypi environment gate (human approval #2) → PyPI
                → examples against PyPI (smoke test)
                → GitHub Release (created last, on purpose)
```

Key properties, and where each is enforced:

- **Only the maintainer can release.** Dispatch requires write access; the `pypi`
  environment requires the maintainer's review; the tag can only be created by the App or
  the maintainer (tag-guard).
- **The reviewed tree is the released tree.** The cut branch is a bare ref to a main
  commit; the merge into `stable` can never introduce changes (stable only ever receives
  cuts of main, so the merge-commit tree always equals the cut tree); `release.yml`
  re-validates the tagged tree and asserts the hatch-vcs version equals the tag.
- **Rejection is consequence-free.** Closing the release PR deletes the cut branch
  (tag-release.yml's cleanup job); re-dispatching force-updates or supersedes cleanly. No
  version is consumed until an artifact reaches TestPyPI.
- **Burned versions.** PyPI and TestPyPI never allow a filename to be re-uploaded, even
  after deletion. A version that reached TestPyPI and didn't complete is therefore dead:
  the retry is the next version (prepare-release skips existing tags automatically). Gaps
  in the version sequence are normal and expected.
- **Nothing user-visible outlives a failed release.** The GitHub Release is created only
  after the PyPI publish succeeds *and* the examples smoke-test the published artifact. A
  run that dies earlier leaves only the tag and, past the TestPyPI stage, a burned number
  (past the PyPI stage, an unannounced-but-live PyPI release the maintainer can yank).
- **`stable` = last approved cut**, not necessarily "last published": if a release fails
  after merge, its changes were still reviewed and stay in stable's history; the next cut's
  diff picks up from there.

### Versioning

[ZeroVer](https://0ver.org/): major stays 0. **Minor** = breaking public-API change or new
feature; **patch** = everything else. "Breaking" is defined against the flagged surfaces:
`__all__` in `__init__.py`, the `RequestHandler` class, the `ServiceProvider` protocol.
`scripts/release_impact.py` recommends the bump by classifying commits and AST-diffing
those surfaces since the last tag; `bump=auto` follows it, `bump=patch|minor` overrides.

The version exists **only as a git tag**. hatch-vcs derives it at build time; untagged
builds get dev versions (`0.2.0.dev3+g1a2b3c4`); `__version__` reads installed package
metadata. There are no version strings, bump commits, or committed CHANGELOG.md — the
changelog is rendered by git-cliff into the release PR body and the GitHub Release notes.

### Release notes

The **GitHub Release for each tag is the canonical, browsable changelog** — there is no
committed `CHANGELOG.md` and, deliberately, no changelog page on the docs site (that would
be a second source to keep in sync for no gain). git-cliff (`cliff.toml`) renders the notes
from Conventional Commits, filtered to consumer-relevant changes: only user-facing commit
types (`feat`/`fix`/`perf`/`refactor`/`docs`/`revert`) whose diff touches `src/pymediate/**`.
The template groups by type, **hoists breaking changes into a `⚠️ Breaking Changes` section
at the top** (under ZeroVer a breaking change is the entire signal of a minor bump), linkifies
the `(#N)` PR reference every squash merge carries, and ends with a **`Full Changelog`
compare link** to the previous tag. The same template feeds the release PR body (`--strip all`
there drops the compare footer, since the tag doesn't exist until merge).

One sharp edge, learned from v0.1.5's empty `[Unreleased]` notes: the `--include-path`
glob **must be quoted** everywhere it appears (`tasks.toml`, `prepare-release.yml`) — an
unquoted cmd-glob is expanded by poe/the shell into absolute paths that match no commit,
silently emptying the changelog rather than failing.

### Examples as release verification

Every `examples/<name>/` is a standalone uv project that declares PyMediate as a normal
dependency (see `examples/README.md` for the contract). The complete architecture example has
one checkout-only editable source; release runs remove it and re-pin every project to the
selected wheel or index version. The examples are the release pipeline's **proxy downstream
users** — the only consumers of the package the pipeline can observe before real ones exist.
The library's own test suite runs against the source tree inside the repo's environment; only
the examples exercise what a release actually changes — the built artifact, resolved from an
index, into a fresh environment, driving the public API the way the docs tell people to. The
design rationale (why standalone uv projects, why outside the library's lint/type/coverage scopes,
why the loose `>=` bound, why four gates rather than one) is recorded in
[ADR 0007](docs/adr/0007-examples-as-release-verification.md).

The runner has four targets: `--check-contract`, `--check-repository`, `--wheel`, and
`--version`. Pull requests to `main` that change the library, an example, or the runner use
both check targets and wheel mode. The Checks workflow validates the release contract and
repository structure, builds the current wheel, and runs every example against it before the
change enters `main`.

The release process then uses the wheel and version targets at four gates. Each gate answers
a different question and is placed at the earliest stage that can answer it:

1. **On the release PR** (required "Examples" check, wheel mode): every example runs
   against a wheel built from the cut itself. *Does this code break downstream users?*
   A breaking change whose examples weren't updated fails *here* — before the merge, so
   closing the PR costs nothing and no version is burned. Consequence: shipping a breaking
   release means updating the examples on main first; until that release publishes, the
   updated examples' standalone `uv run pytest` fails against released PyPI — a bounded,
   expected window that Dependabot's post-release re-lock closes.
2. **In release.yml, before the TestPyPI publish** (wheel mode, against the built dist
   artifact): *does the release artifact, with today's dependency resolution, still work?*
   The runner re-resolves each example's dependencies fresh from PyPI, so a release PR
   that sat open lets them drift between check time and tag time; and the PR check's wheel
   carries a hatch-vcs dev version while this one is the real, release-versioned artifact.
   Failing here is free; the same failure one stage later burns the version.
3. **After the TestPyPI publish** (index mode): each example re-pins to the candidate
   version via an *explicit* uv index — only pymediate resolves from TestPyPI while its
   dependencies stay on real PyPI. *Does the publish-and-install path work?* All examples
   must pass before the PyPI gate is offered.
4. **After the PyPI publish** (index mode, against `pypi.org`): the smoke test — the only
   stage that exercises the exact artifact users install, from the index they install it
   from (PyPI and TestPyPI are separate services: separate registration, upload, and CDN).
   *Does the thing we just shipped actually work?* It gates the GitHub Release: the
   announcement is only created once the announced artifact is proven installable. A
   failure here can't unpublish — it withholds the announcement while the maintainer
   investigates, and re-running the failed jobs resumes the pipeline.

## Enforcement inventory

### Rulesets

| Ruleset | Target | Rules | Bypass |
|---|---|---|---|
| `main-guard` | `main` | PR required (1 approval incl. of the last push, squash only), required checks (strict), CodeQL, no deletion/force-push | maintainer (lane 1) |
| `stable-guard` | `stable` | PR required (1 approval incl. code owner + last push, stale reviews dismissed, threads resolved, merge commit only), required checks incl. Release Test Results + Examples, CodeQL, no deletion/force-push | **none** |
| `branch-guard` | all other branches | no create/update/delete | maintainer, Dependabot, releaser App |
| `tag-guard` | all tags | no create/update/delete | maintainer, releaser App |

Notes: stable-guard deliberately has **no bypass actors** — merging a red release PR
requires editing the ruleset itself, which is the break-glass. Its review requirements
(code owner + last-push approval) work because release PRs are authored and pushed by the
releaser App, so the maintainer's approval satisfies both; the flip side is that a cut
branch the maintainer pushes to by hand can no longer be self-approved — the remedy stays
the same as ever: close the PR, fix on main, re-cut. Its up-to-date-with-base
requirement is off by design: a cut branch never contains stable's previous merge commit,
and the merge result tree always equals the cut tree, so "stale" is impossible in any way
that matters. Merge commits (not squash) are required on stable because a squash would
orphan the merge-base and the next release PR's diff would regress to the beginning of
history.

### Identities and credentials

| Identity | Used for | Credential |
|---|---|---|
| Maintainer (`sina-al`) | lanes 1–3, release initiation and approvals | — |
| `pymediate-releaser` GitHub App | pushing cut branches, opening/closing release PRs, tagging, deleting rejected cuts | short-lived installation tokens minted per job (`PYMEDIATE_RELEASER_APP_ID` var + `PYMEDIATE_RELEASER_PRIVATE_KEY` secret) |
| Dependabot | lane 3 | GitHub-managed |
| OIDC Trusted Publishing | TestPyPI + PyPI uploads | none stored — federated per-run; registered on **both** pypi.org and test.pypi.org |
| Build attestations | provenance for dist artifacts | Sigstore via `actions/attest-build-provenance`; verify with `gh attestation verify dist/*.whl -R sina-al/pymediate` |

### Environments

| Environment | Protection |
|---|---|
| `pypi` | required reviewer: maintainer (human approval #2) |
| `testpypi` | none (failing here is cheap by design) |
| `documentation`, `github-pages` | deploy-from-main only |

### Residual risks, accepted deliberately

- The maintainer is a repo admin and can edit rulesets; no configuration on GitHub can
  bind an admin. Mitigations: stable-guard has no standing bypass (breaking glass is an
  explicit, logged act), and `release.yml` independently re-validates the tagged tree.
- Auto-merged Dependabot patches land without human eyes. Scope is limited to
  patch-level bumps that pass every required check.

## How-to

- **Cut a release**: `gh workflow run prepare-release.yml -f bump=auto` (or the `/release`
  skill, or the Actions tab from any browser). Review the PR, merge, approve the `pypi`
  gate when it pauses there.
- **Reject a release**: close the PR. That's it.
- **Retry after a failure**: fix the cause on main if needed, re-dispatch; the version
  self-advances past anything burned.
- **Hotfix**: main is the trunk — land the fix there (any lane), then cut a release. There
  are no release branches to backport to.
- **Verify a wheel's provenance**: `gh attestation verify pymediate-*.whl -R sina-al/pymediate`.

## Work tracking

GitHub Issues, labels `roadmap` (product/features), `process` (repo automation),
`ops-overhaul` (the July 2026 effort that built this model). `ROADMAP.md` is a pointer,
not a database. Scriptable via `gh issue`/`gh project`.
