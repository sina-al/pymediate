---
name: edict
description: Turn a raw maintainer request into an implementation-ready GitHub issue via a structured interview — research the repo, ask decision-shaped questions, draft a requirements-first spec, file it immediately as a draft-labeled issue, then revise it in place until the maintainer approves and the `draft` label comes off. Use whenever the maintainer says "file an issue", "put this on my list", "track this", "add to the roadmap", or states a request or idea they want captured for later implementation — even a one-liner.
---

# Edict

Read `.claude/skills/edict/SKILL.md` in full and follow it as the canonical workflow. Treat
`/edict` as this skill's name.

The canonical workflow references Claude Code tool names (`AskUserQuestion`, GitHub MCP
tools). Under other providers, substitute the equivalent facility: any interactive
question/confirmation mechanism for the interview and the Step 5 gate, and `gh` or the GitHub
API for issue operations. The invariants are provider-neutral: interview before drafting,
file with the `draft` label, never remove that label without the maintainer's explicit
approval.
