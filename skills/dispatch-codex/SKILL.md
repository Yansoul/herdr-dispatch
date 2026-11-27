---
name: dispatch-codex
description: Dispatch tasks to Codex or omp agents in isolated Herdr/hc worktrees. Prefers native codex CLI by default, and also supports omp through magpie (default model gpt-6.2-sol) as fallback or via --runtime omp. Plan, supervise, verify, publish, independently review and merge each lane. Use for dispatch-codex, codex task dispatch, parallel Herdr/hc worktrees, or resuming a dispatch-codex run.
argument-hint: '<tasks> [--runtime codex|omp|auto] [--model model-id-or-magpie-selector] [--thinking level] [--lanes N] [--base ref] [--no-yolo] [--yolo] [--draft] [--no-pr] [--no-automerge] [--resume] [--run id] [--no-loop]'
allowed-tools: Read, Write, Edit, Glob, Grep, TodoWrite, AskUserQuestion, Skill, Bash(herdr:*), Bash(hc:*), Bash(codex:*), Bash(omp:*), Bash(magpie:*), Bash(git:*), Bash(gh:*), Bash(jq:*), Bash(python3:*), Bash(mkdir:*), Bash(ls:*), Bash(test:*), Bash(date:*), Bash(mv:*), Bash(cat:*), Bash(printf:*)
---

# dispatch-codex

This entry supports **both** runtimes and **prefers native `codex` CLI** by default:

- **`codex` (preferred default):** runs the native `codex` CLI in goal mode (`agent_kind: "codex"`), using [references/codex-driver.md](references/codex-driver.md).
- **`omp` (supported alternative / fallback):** runs `omp` through `magpie` requesting **gpt-6.2-sol** by default (`agent_kind: "omp"`), using [references/routing.md](references/routing.md) and [references/driver.md](references/driver.md).

The raw request is the skill arguments, or the user's task text when no arguments were passed.

## Runtime selection (`--runtime codex|omp|auto`, default `auto`)

1. **`--runtime codex`**: require native `codex` CLI (`codex --version` resolves cleanly, and on `herdr` `herdr agent start --help` supports `codex`). Do not silently fall back to `omp`. Reject `--model magpie/...` as conflicting with `--runtime codex`.
2. **`--runtime omp`**: require `omp` through `magpie` (`references/routing.md` + `references/driver.md`). Do not launch native `codex`.
3. **`--runtime auto` (default when omitted)**:
   - If the user explicitly supplied a `magpie/...` selector in `--model`, select `omp` (since `magpie/...` is a magpie/omp route).
   - Otherwise, check native `codex` availability first (`codex --version`, plus `herdr agent start --help` supporting `codex` on `herdr`, or `hc exec --cwd <repo> -- codex --version` on `hc`).
   - If native `codex` is available, select **`codex`** (`agent_kind: "codex"`).
   - If native `codex` is unavailable, fall back to **`omp`** through `magpie` (`agent_kind: "omp"`, default model `gpt-6.2-sol`) and report in the §3 summary why `codex` was skipped.
4. **On `--resume`**: read the recorded `agent_kind` from `state.json` (treat legacy `dispatch-codex` state files without `agent_kind` as `"codex"`). Use `references/codex-driver.md` for `"codex"` runs and `references/driver.md` for `"omp"` runs. Reject `--runtime` changes on resume — switching runtimes requires a new run.

## Reading order

Read [references/entry.md](references/entry.md) first and follow §0–§1. For `dispatch-codex`, the dual-runtime rules above override the `omp`-only wording in `references/entry.md`, `references/plan.md`, and `references/supervise.md` whenever `agent_kind` is `"codex"`.

- When running **`codex`**: skip `references/routing.md`, follow [references/plan.md](references/plan.md) (§2–§5b), [references/codex-driver.md](references/codex-driver.md) (§5a, §5c, §6a, §6c, §6d, §6g, §6h), and [references/supervise.md](references/supervise.md) (§6b, §6e–§6f, §6i–§6j, §7–§8).
- When running **`omp`**: follow [references/routing.md](references/routing.md), [references/plan.md](references/plan.md), [references/driver.md](references/driver.md), and [references/supervise.md](references/supervise.md).

