# Native Codex CLI driver — §5a, §5c, §6a, §6c, §6d, §6g, §6h

Used by `dispatch-codex` whenever the selected or recorded runtime is `codex` (`agent_kind: "codex"`).
The agent-independent halves remain `references/plan.md` (§2–§4, §5b) and `references/supervise.md`
(§6b, §6e, §6f, §6i, §6j, §7, §8). When `dispatch-codex` runs in `omp` mode (`agent_kind: "omp"`),
use `references/routing.md` and `references/driver.md` instead — never mix commands across drivers.

Claims marked **(verified)** were checked against codex **0.151.0** on `herdr`. §2 records the
version actually found; a mismatch is a report line, not an abort.

---

## §5a Preflight

A fresh worktree is not a working environment: no `node_modules/`, no `.env`, no `.venv`, because
those are untracked or ignored.

```text
herdr: herdr pane run <pane> "codex --version"
hc:    hc exec --cwd <checkout> -- codex --version
```

Run `--version`, not `command -v`: on an asdf/mise machine the shim can resolve even when the
worktree has no tool version configured, causing launch to fail at runtime. On `herdr`, poll
`herdr pane read <pane> --source visible` (`herdr pane read` without `--source` returns empty with
exit code 0, and `wait-output` only matches future output). On `herdr`, also confirm once per run
that `herdr agent start --help` supports `--kind codex`.

- `codex` not found or refuses to resolve:
  - Under `--runtime auto` (before lanes are created), fall back to `omp` through `magpie`
    (`references/routing.md` + `references/driver.md`) and report why `codex` was skipped.
  - Under `--runtime codex` (or per-lane after `codex` was selected), stop that lane and report it
    (for asdf/mise, suggest adding the tool to `.tool-versions` or setting a global default).
- Dependencies missing → install the repository's required dependencies in the lane checkout
  **before** starting the agent (`herdr` needs the pane back at an idle interactive prompt).
- `.env` or other secrets missing → **ask the user** before symlinking them. Never copy secrets.

Write `.dispatch/TASK.md` (§5b in `references/plan.md`) before launch.

Record `schema_version: 2`, `agent_kind: "codex"`, codex version, `approval_mode` (`yolo` by
default, `no-yolo` under `--no-yolo`), optional `model` / `thinking` (only when explicitly passed
via `--model` / `--thinking`), and `launch_state: "prepared"`. Keep session uuid null until
observed. Shell-quote every argument; never concatenate untrusted task text into a shell program.

---

## §5c Launch codex and set the goal

Launch codex with **no positional prompt**. The lane is driven by a codex **goal** (`/goal`),
which is a slash command and cannot ride along on argv (`The session must start before you can set
a goal`). Send `/goal` only after the composer is confirmed visible — a startup modal eats input.

```text
herdr: herdr agent start <lane> --kind codex --pane <pane> --timeout 120000 -- \
  --no-alt-screen -c 'tui.status_line=["context-remaining"]' \
  [--dangerously-bypass-approvals-and-sandbox] \
  [-m <model>] [-c model_reasoning_effort=<thinking>]

hc:    hc run --bg --name <lane> --cwd <checkout> --outlive-parent --keep \
  --label dispatch.skill=dispatch-codex --label dispatch.run=<run-id> --label dispatch.lane=<lane> \
  -- codex \
  --no-alt-screen -c 'tui.status_line=["context-remaining"]' \
  [--dangerously-bypass-approvals-and-sandbox] \
  [-m <model>] [-c model_reasoning_effort=<thinking>]
```

Why each part:

- `--no-alt-screen` puts codex inline so scrollback reads work while the agent is busy.
- `-c 'tui.status_line=["context-remaining"]'` forces the status row to `Context N% left`.
- `--timeout 120000` on `herdr` accommodates cold start + MCP boot.
- On `hc`, `--bg`, `--outlive-parent`, and `--keep` are load-bearing: `--bg` returns immediately,
  `--outlive-parent` keeps the lane alive if the orchestrator exits, and `--keep` returns the
  terminal to a shell if codex exits. Record the new terminal's address from `--json` / `hc ls`.
- Never pass `--full-auto` — removed in codex 0.151.0, it errors at launch.
- `--dangerously-bypass-approvals-and-sandbox` is **on by default** (`yolo`). Drop it **only** when
  the user passed `--no-yolo`, in which case the lane inherits the user's own codex approval config
  and every overlay is handled in §6g. Explain in the §3 summary that neither mode is a sandbox.
- Only pass `-m <model>` when `--model` was explicitly provided (and is not a `magpie/...`
  selector); otherwise codex uses the user's configured default model. Only pass
  `-c model_reasoning_effort=<thinking>` when `--thinking` was explicitly provided.

**Verify readiness before sending `/goal`.** `agent_started` / `idle` / `interactive_ready: true`
does NOT prove codex is ready. On any fresh worktree codex has not trusted before, it parks on a
modal reading `Do you trust the contents of this directory?` with `1. Yes, continue`.

```text
herdr: herdr agent read <lane> --source visible
hc:    hc read <lane>
```

If it matches `Do you trust the contents of this directory`, send `enter` once
(`herdr agent send-keys <lane> enter` / `hc keys <lane> enter`), then re-read until the version
banner and the `› Ask Codex to do anything` composer are visible.

**Then set the goal** — one call, only after the composer is visible:

```text
herdr: herdr agent prompt <lane> "/goal Work through .dispatch/TASK.md in this directory: follow its plan in order, satisfy every acceptance criterion, keep .dispatch/progress.md updated after every checklist item, and finish by writing .dispatch/DONE and running the notify-back command TASK.md gives you."
hc:    hc send <lane> "/goal Work through .dispatch/TASK.md in this directory: follow its plan in order, satisfy every acceptance criterion, keep .dispatch/progress.md updated after every checklist item, and finish by writing .dispatch/DONE and running the notify-back command TASK.md gives you."
```

Key properties of codex goals:

- The objective is thread-scoped and persistent: codex auto-continues across turns toward it.
- Goal state lives in `~/.codex/goals_1.sqlite` (root path — **not** `~/.codex/sqlite/goals_1.sqlite`,
  which exists and stays empty), keyed by session uuid, with status `active` / `paused` / `blocked`
  / `usage_limited` / `budget_limited` / `complete`.
- **Set the goal once.** A second `/goal <objective>` over an `active` (or `paused`) goal opens a
  `Replace goal?` selection list whose highlighted default is **Replace** (§6d handles it if ever
  seen). Only over a `complete` goal or a fresh thread does `/goal` start dialog-free.

Record the lane as phase `implementing` with its session uuid in the state file. If `/goal` errors
or is unavailable, record `goal_skipped` with the reason, surface it in §8, and fall back to a
one-shot prompt:

```text
herdr: herdr agent prompt <lane> "Read .dispatch/TASK.md in this directory and work through its checklist. Keep .dispatch/progress.md updated after every item. Write .dispatch/DONE when everything is finished and verified, then run the notify-back command TASK.md gives you."
hc:    hc send <lane> "Read .dispatch/TASK.md in this directory and work through its checklist. Keep .dispatch/progress.md updated after every item. Write .dispatch/DONE when everything is finished and verified, then run the notify-back command TASK.md gives you."
```

Start every lane before supervising any of them.

---

## §6a Probe one lane — write the lane-state helper once

If `~/.claude/dispatch-codex/bin/lane_state.py` is absent, write it, then call
`python3 ~/.claude/dispatch-codex/bin/lane_state.py <session-uuid>`.

Obtaining the session uuid:

- On `herdr`: `herdr agent get <lane> | jq -r '.result.agent.agent_session.value'`.
- On `hc`: read `hc get <lane> --json` for a reported session id if present; otherwise locate the
  newest `~/.codex/sessions/YYYY/MM/DD/rollout-*-<uuid>.jsonl` created at or after this lane's
  launch whose `session_meta` header `cwd` matches `<checkout>`, and record that `<uuid>` in state.

The rollout path is `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`. Record the uuid in
state (it also enables `codex resume <uuid>`). After a §6h `/new` restart, codex assigns a **new**
uuid only after the fresh thread's *first turn* (verified) — wait for it to change and re-record.

The helper reads only the **tail** (~2 MB) of the rollout and reports the probe contract's fields:

- `used_pct` — `last_token_usage.input_tokens / model_context_window × 100` from the last
  `token_count` event. Use `last_token_usage`, **not** `total_token_usage` (cumulative billing).
- `turn_state` — `complete` when the last of `task_started` / `task_complete` / `turn_aborted` is
  `task_complete`, else `working`. Keep raw `last_event`.
- `compactions` — count of top-level `{"type":"compacted"}` records.
- `mtime` — the rollout's modification time, for stall detection.
- `out_of_room` — whether the tail contains codex's `ran out of room` marker.
- `goal_status` and `goal_tokens` — read-only query of `~/.codex/goals_1.sqlite`
  (`SELECT status, tokens_used FROM thread_goals WHERE thread_id = ?`, the session uuid).

---

## §6c Classify each lane, in this order

| Class | Test | Action |
| --- | --- | --- |
| `terminal` | phase is `published`, `failed`, user-paused, or `verified` with a recorded §6f degrade reason | Skip — report only; cleanup only per shared contract |
| `unpublished` | phase is `verified`, `publish_attempts` < 3, no recorded degrade reason, and `pushed_sha` is missing or behind branch HEAD, or `pr_url` is missing with PRs enabled | Retry publish (§6f) |
| `done` | `.dispatch/DONE` exists **and** `turn_state == complete` | Verify (§6e), publish (§6f), mark terminal |
| `blocked` | mux reports `blocked` | Read visible terminal, handle (§6g) |
| `hard_fail` | `out_of_room` (§6a), and no §6h restart is recorded in flight | Compaction cannot save it — restart per §6h's recipe and re-prime from `.dispatch/` |
| `goal_parked` | `goal_status` is `paused`, `usage_limited`, or `budget_limited` | Resume or surface, per state (§6d) |
| `goal_blocked` | `goal_status` is `blocked` | Steer or escalate (§6d) |
| `stalled` | mux state/seq **and** rollout `mtime` both unchanged ≥ 15 min, and `goal_status` is not `complete` | Read visible terminal once: parked selection list → §6d/§6g; idle composer over unfinished work → `idle_incomplete`; exited process → §6h relaunch; otherwise escalate |
| `hot` | `used_pct ≥ 70` **and** `turn_state == complete` | Compact (§6h) |
| `idle_incomplete` | mux reports `done`/`idle`, no `DONE` file, **and** `goal_status` is not `active` | Read `progress.md`, send a specific continuation prompt, record the nudge; a re-nudge with no progress since the last one escalates instead |
| `working` | otherwise | Leave it alone |

An `unknown` status is an anomaly to surface, never a completion.

---

## §6d Steer a goal lane

Every input below is subject to §6b's prompt guard (read visible terminal immediately before
sending; never send a prompt into a parked selection list).

**`paused` / `usage_limited` / `budget_limited`:**

```text
herdr: herdr agent prompt <lane> "/goal resume"
hc:    hc send <lane> "/goal resume"
```

- `paused` — you only pause when the user asks (send `/goal pause` and record
  `pause: {origin: user, at: <sweep time>}`). A `paused` goal without that record was paused by
  the user at the keyboard: do **not** resume it; escalate once as paused-awaiting-user.
- `usage_limited` — the shared Codex account hit its rate window. Send `/goal resume` at most once
  per sweep; let the sweep cadence serve as retry.
- `budget_limited` — someone configured a token budget deliberately: escalate once and resume only
  when the user says so.

**`blocked`:** Read `.dispatch/progress.md` and the visible terminal. If the answer is already
within the §3 plan, send a corrective prompt (waiting for the turn to settle) and **then** send
`/goal resume` (codex refuses slash commands mid-turn; clear any rejected slash command with
`ctrl+u` then `ctrl+k`). If the blocker is outside plan scope (missing secret, broken upstream,
contradiction), escalate to the user with the blocker quoted.

**`complete` but no `DONE`:** Falls through to `idle_incomplete`; send a guarded continuation
prompt asking the lane to reconcile `TASK.md`, commit, write `.dispatch/DONE`, and run notify-back.

**A `Replace goal?` selection list on screen:** Answer **only** with keys:
`herdr agent send-keys <lane> 2` / `hc keys <lane> 2` cancels and keeps the current goal.

---

## §6g Handle a blocked lane

Under default `yolo` mode codex raises no approval overlays, so `blocked` there is usually a trust
modal (§5c) or a mux misclassification. Read the visible terminal first.

Under `--no-yolo`, codex approval overlays are titled `Would you like to run the following
command?` / `make the following edits?` / `grant these permissions?` / `send input to the existing
terminal?` with hotkeys `y` approve, `a` approve-for-session, `p` approve-for-prefix, `d` deny,
`c` cancel.

- Benign and confined to the lane's own checkout → approve with
  `herdr agent send-keys <lane> y` / `hc keys <lane> y`.
- Notify-back exception: if the quoted command is **exactly** the lane's §5b notify-back command
  targeting the recorded `orchestrator_pane` with this run id and lane name and nothing chained,
  approve with `y`.
- Anything leaving the lane's blast radius (`git push`, `gh pr create`, force operations, `sudo`,
  deleting outside the checkout, reading credentials, writing to a network target) → **do not
  approve**. Pause/escalate and surface to the user.

Clear any modal with `send-keys` / `keys` before sending a prompt.

---

## §6h Compact, restart, and recover a lane

**Compact (only when `turn_state == complete`):**

```text
herdr: herdr agent prompt <lane> "/compact" --wait --until idle --timeout 120000
hc:    hc send <lane> "/compact" --wait
```

- If a slash command is rejected mid-turn (e.g. `agent_prompt_stalled` / `Unrecognized command`),
  clear the composer with `ctrl+u` then `ctrl+k` and retry on the next sweep.
- Verify success by confirming the rollout's top-level `{"type":"compacted"}` count increased (on
  screen: `Context compacted`). Transient `Stream disconnected` / `Reconnecting…` notices are
  harmless if compaction completes.
- After compacting a goal lane, do not re-prime immediately: check on the next sweep that
  `goal_status` is still `active` and rollout `mtime` advances; if stuck, send a guarded
  `/goal resume`. For a `goal_skipped` lane, re-send the §5c one-shot prompt.
- **Stop after 3 compactions** and hand off via the restart recipe below.

**Restart recipe (for `hard_fail` or 3-compaction handoff while codex is alive):**

1. Record `restarting: true` on the lane and rewrite the state file atomically.
2. Send `/new` (`herdr agent prompt <lane> "/new"` / `hc send <lane> "/new"`).
3. Re-prime with §5c's exact `/goal` call (or one-shot prompt for `goal_skipped`).
4. Wait until the reported session uuid **differs** from the previous recorded uuid (it updates on
   the new thread's first turn), then record the new uuid and clear `restarting`.

**Process exited (agent absent from recorded terminal):**

Verify the recorded terminal is back at an idle shell (on `hc`, `--keep` returns it to a shell)
and the recorded session uuid is known. Relaunch with `codex resume <uuid>` using the same flags
(`--no-alt-screen`, `-c 'tui.status_line=["context-remaining"]'`, approval/model/thinking flags) —
on `herdr` via `herdr agent start <lane> --kind codex --pane <pane> --timeout 120000 -- resume <uuid> ...`,
on `hc` via `hc send <lane> "codex resume <uuid> ..."`. If the process is hung rather than exited,
do not spawn a duplicate; inspect visible state and escalate.
