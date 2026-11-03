---
name: dispatch-glm
description: Dispatch tasks to omp agents in isolated Herdr worktrees using the glm magpie model preset. Plan, supervise, verify, publish, independently review and merge each lane. Use for dispatch-glm, glm task dispatch, parallel Herdr worktrees, or resuming this preset's run. The runtime is always omp.
argument-hint: '<tasks> [--model magpie/provider/model] [--thinking level] [--lanes N] [--base ref] [--no-yolo] [--yolo] [--draft] [--no-pr] [--no-automerge] [--resume] [--run id] [--no-loop]'
allowed-tools: Read, Write, Edit, Glob, Grep, TodoWrite, AskUserQuestion, Skill, Bash(herdr:*), Bash(omp:*), Bash(magpie:*), Bash(git:*), Bash(gh:*), Bash(jq:*), Bash(python3:*), Bash(mkdir:*), Bash(test:*), Bash(date:*), Bash(mv:*), Bash(cat:*), Bash(printf:*)
---

# dispatch-glm

This entry selects the **glm** preset; execution always uses **omp through magpie**. The raw request is the skill arguments, or the user's task text when no arguments were passed.

Read [references/entry.md](references/entry.md) first and follow §0–§1. It defines the shared invariants, flags and legacy-run gate. Then follow its routing, planning, runtime and supervision references. Do not launch the CLI named by this preset or reuse its old driver protocol.
