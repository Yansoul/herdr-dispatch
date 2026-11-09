---
name: dispatch-omp
description: Dispatch tasks to omp agents in isolated Herdr worktrees using an explicitly requested model or magpie catalog selector. Magpie decides suppliers and routing unless the user explicitly supplies a selector. Plan, supervise, verify, publish, independently review and merge each lane. Use for dispatch-omp, omp task dispatch, parallel Herdr worktrees, or resuming this preset's run. The runtime is always omp.
argument-hint: '<tasks> [--model model-id-or-magpie-selector] [--thinking level] [--lanes N] [--base ref] [--no-yolo] [--yolo] [--draft] [--no-pr] [--no-automerge] [--resume] [--run id] [--no-loop]'
allowed-tools: Read, Write, Edit, Glob, Grep, TodoWrite, AskUserQuestion, Skill, Bash(herdr:*), Bash(hc:*), Bash(omp:*), Bash(magpie:*), Bash(git:*), Bash(gh:*), Bash(jq:*), Bash(python3:*), Bash(mkdir:*), Bash(test:*), Bash(date:*), Bash(mv:*), Bash(cat:*), Bash(printf:*)
---

# dispatch-omp

This entry accepts **a model ID or an exact magpie catalog selector**; execution always uses **omp through magpie**. The skill resolves model IDs without a supplier preference and honors exact selectors explicitly supplied by the user. Magpie owns routing, accounts, and failover. The raw request is the skill arguments, or the user's task text when no arguments were passed.

Read [references/entry.md](references/entry.md) first and follow §0–§1. It defines the shared invariants, flags and legacy-run gate. Then follow its routing, planning, runtime and supervision references. Do not launch the CLI named by this preset or reuse its old driver protocol.
