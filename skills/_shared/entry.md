# Unified dispatch — §0 and §1

Every entry runs **omp**, with every model request routed through **magpie**. The entry's name selects a model preset, never a different executable. Read this file on every invocation, `routing.md` before a fresh run, `plan.md` for §2–§5b, `driver.md` for runtime operations and `supervise.md` for verification/publication. References are relative to this file. They are shared sources materialized by supported installers.

## §0 Invariants

1. State is `~/.claude/<skill-name>/<run-id>/state.json`; this historical directory is bookkeeping, not the runtime. Record `schema_version: 2`, `agent_kind: "omp"`. Read it before every sweep and replace atomically after each mutation. Never infer lane ownership from a reusable name.
2. A lane owns one git worktree created for this run (`herdr worktree create` on `herdr`, plain `git worktree add` on `hc`). The orchestrator plans, verifies, publishes, independently reviews and merges; the lane implements and commits only. `.dispatch/DONE` and a completed goal are claims that require §6e verification.
3. Select a model, then resolve its magpie-managed group or sole catalog entry under routing.md, or honor the user's exact magpie selector. Pin the resulting full selector, thinking level and role routes per lane. Suppliers, accounts and failover belong to magpie; never infer a supplier from a skill name or change global omp/magpie settings. No fallback outside magpie and no native Codex/Cursor/Devin CLI execution.
4. Control only recorded terminals/sessions — herdr panes on `herdr`, hc terminals on `hc`. Never focus panes, stop the Herdr server or the hc core, force-push, or delete live worktrees. Post-merge cleanup follows §8.1 and is limited to this run's recorded resources. That includes what a lane started on the machine: its processes are stopped only through the list-first tool in supervise.md §8.2 and its containers only by the run's `dispatch.run` label. Never kill by name pattern, never run a kill loop whose targets were not printed first, never `docker ... prune`, and never stop Docker Desktop, Postgres.app or any other service this run did not start.
5. Probe bounded session metadata, not entire conversation bodies. Unknown state remains unknown. Never equate an idle terminal with task completion or invent context percentages.
6. Legacy state without `schema_version: 2` and `agent_kind: "omp"` is incompatible. Report its runtime and path, leave its files/processes untouched, and require finishing it with the previous plugin revision or an explicitly planned fresh run. Never relabel or resume it as omp.

## §1 Gate and parse

Detect the multiplexer backend and record it as `mux` in the state file. The two environments are mutually exclusive:

- `herdr` (classic Herdr): `test "${HERDR_ENV:-}" = 1`, a nonempty `HERDR_PANE_ID`, and successful `herdr agent list`. The orchestrator terminal id is `$HERDR_PANE_ID`. Read the installed Herdr skill before controlling panes, and check `herdr agent start --help` supports `omp`.
- `hc` (herdr-core): a nonempty `HC_TERMINAL_ID` and successful `hc ls`. The orchestrator terminal id is `$HC_TERMINAL_ID`. Lanes launch as `hc run` children of this terminal; their status transitions are reported back to it automatically.

If neither backend's checks pass, stop; do not install or start either multiplexer. On `--resume` the recorded `mux` must match the detected backend — a mismatch means the run's lanes live in the other system, so report it and steer nothing. Runs recorded before `mux` existed are `herdr` runs.

Throughout the references **terminal** means a herdr pane or an hc terminal, and each multiplexer operation is written in both forms: `herdr: …` / `hc: …`. Quick map:

| Operation | `herdr` | `hc` |
| --- | --- | --- |
| List every agent | `herdr agent list` | `hc ls --json` |
| Get one | `herdr agent get <name>` | `hc get <t> --json` |
| Read screen | `herdr agent read <name> --source visible` | `hc read <t>` |
| Prompt | `herdr agent prompt <name> "…" [--wait]` | `hc send <t> "…" [--wait]` |
| Keys | `herdr agent send-keys <name> <keys>` | `hc keys <t> <keys>` |
| Wait settled | `herdr agent wait <name>` | `hc wait <t>` |

| Flag | Meaning | Default |
| --- | --- | --- |
| `--model <model-id>` | Model identity or any user-supplied exact magpie chat selector; preserve explicit selectors and resolve model identities via routing.md | preset model from routing.md; required for dispatch-omp |
| `--thinking <level>` | Explicit catalog-supported reasoning level | high when supported; otherwise routing.md |
| `--lanes N` | Concurrent lane cap, integer 1–16 | 16 |
| `--base <ref>` | Branch base | origin/current when available, otherwise current |
| `--no-yolo` | Explicit omp `--approval-mode always-ask` | off |
| `--yolo` | Explicit omp `--approval-mode yolo` | on |
| `--draft` | Draft PR, never auto-ready or auto-merge | off |
| `--no-pr` | Push verified branch, print PR command | off |
| `--no-automerge` | Stop at open PR | off |
| `--resume` | One sweep of recorded run, then maintain its timer | off |
| `--run <id>` | Select a specific existing run with --resume | infer only if exactly one matches |
| `--no-loop` | Disable automatic supervision timer | off |

Reject conflicting approval flags, malformed values and unknown flags before creating resources. `--compact-at` is removed: omp performs automatic context maintenance. Explain the replacement; do not silently ignore it. `--no-worktree` is unsupported. A worktree isolates edits, not operating-system access; approval bypass is not a sandbox.

On `--resume`, find state files under this entry's directory matching the canonical repo path. Honor `--run` exactly (validate as a single directory name, no traversal); otherwise select the sole nonterminal run, asking only if ambiguous. An explicit run may be terminal for reporting/cleanup. Apply the legacy gate **before any write or agent control**. Do not re-resolve presets, overwrite model routes or reinterpret a saved run's flags from current defaults. Reject model/thinking/approval changes during resume and explain that they require a new run. An explicit `--no-loop` may stop this run's recorded timer. Read driver and supervise, then sweep.

With no task and no --resume, ask for the task. For fresh work, read routing.md and plan.md. A dispatch request authorizes routine lane grouping and creation of the worktrees, workspaces and panes needed for that task. Show the concrete lane plan and selected routes, then proceed directly under §3 without asking for lane/pane confirmation. Ask only about unresolved scope or material choices that require the user's decision.
