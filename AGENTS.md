# Codex repository guidance

This repository supports both Codex and Claude Code. Keep the Claude configuration intact.

Before making changes, read `.claude/CLAUDE.md` in full and treat it as the canonical
repository guidance. Also read `.claude/context/api-signatures.md` when work touches the
public API; Claude imports that generated file automatically, while Codex must load it
explicitly.

Provider-neutral interpretation:

- References to "Claude", "agentic work", or `CLAUDE.md` apply equally to Codex.
- References such as `/adr` or `/release` mean the corresponding project skill in
  `.agents/skills/`.
- Do not run or reproduce `.claude/hooks/`; their reminders are already represented by the
  durable repository guidance.
- Preserve `.claude/` as the canonical source for shared instructions and workflows. Keep
  Codex compatibility files thin so the two setups do not drift.
- When changing shared guidance or a shared skill, update the canonical `.claude` file first,
  then update a Codex wrapper only if its trigger or provider-specific behavior changed.

When working under `docs/`, also follow `docs/AGENTS.md`.
