# Devin driver — §5a, §5c, §6a, §6c, §6d, §6g, §6h

Everything in `dispatch-devin` that depends on devin itself. The agent-independent halves are
`references/plan.md` (§2–§4, §5b) and `references/supervise.md` (§6b, §6e–§6f, §6i, §7, §8);
§0 and §1 are in `../SKILL.md`.

Claims marked **(verified)** were checked against devin CLI **3000.10.27** on this machine. §2
records the version it actually finds; a mismatch is a report line, not an abort. Devin's model is
server-side (`swe-2-max` at verification time) and can change under a fixed CLI version — treat
UI-wording claims as the first thing to re-check when behaviour drifts.

---

## §5a Pre-flight the pane

A fresh worktree is not a working environment: no `node_modules/`, no `.env`, no `.venv`, because
those are untracked or ignored.

    herdr pane run <pane> "devin --version"

Run the version, not `command -v` (same asdf-shim trap as every other agent: the shim can resolve
while the worktree has no `.tool-versions` entry, and then the launch dies inside `agent start`).
Poll `herdr pane read <pane> --source visible` for the version string — `herdr pane read` with
**no `--source`** returns empty output with exit code 0, and `herdr pane wait-output` only matches
output arriving *after* the call (verified herdr traps, agent-independent).

- `devin` not found, or the version refuses to resolve → stop that lane and report it.
  `agent start --kind devin` resolves the executable from the pane's own login shell and args cannot
  redirect it.
- Dependencies missing → run the repo's install command in the pane and let it finish **before**
  starting the agent; `agent start` needs a pane at an idle interactive prompt.
- `.env` or other secrets missing → **ask the user** whether to symlink them. Never copy secrets.
- Devin must be logged in (`devin auth`); an unauthenticated lane starts fine and only fails at the
  first prompt, so check once per run (§2's agent preflight): `devin doctor` exits clean when the
  local configuration is sane (verified), and the §5c readiness read doubles as the auth check — an
  unauthenticated devin shows a login prompt instead of the composer.

Then write the brief (§5b in `references/plan.md`) before launching.

---

## §5c Launch devin and prime the lane

    herdr agent start <lane> --kind devin --pane <pane> --timeout 120000 -- \
      --permission-mode dangerous

Why each part:

- `--permission-mode dangerous` is **on by default** (yolo): lanes run unattended and an approval
  overlay stalls a lane until the next sweep notices it, so approvals are traded away for
  throughput. Verified: the devin banner shows `(bypass permissions on)` and the session row records
  `agent_mode: bypass`. Drop the flag **only** when the user passed `--no-yolo`; the lane then runs
  under the user's own devin config (default mode `auto`: read-only tools auto-approved, everything
  else prompts) and every overlay is handled in §6g. Under `--no-yolo` the dangerous flag is simply
  omitted — omitting it is what makes the lane inherit the user's config.
- Devin's `--sandbox` (seatbelt/bwrap, research preview) is **not** passed: it is off by default and
  unverified under herdr. So yolo here trades away approvals only — there is no sandbox in either
  posture, and the worktree is the only boundary. That is why §3 asks for confirmation, why §1's
  worktree rule has no opt-out, and why §5b's boundaries are load-bearing. Never widen a lane's
  blast radius beyond that — no lane briefed to push, merge, or open a PR (§0.6).
- `--timeout 120000` because devin cold start is several seconds; the 30 s default is too tight on
  a slow machine.

**The three lines §3 owes the user, in this driver's words:**

- approval posture — `yolo（--permission-mode dangerous，绕过全部审批；devin 的 --sandbox 默认未启用，worktree
  是唯一边界）` by default, or `--no-yolo（沿用你自己的 devin 权限配置，审批弹窗由监督循环处理）`;
- how the lane is driven — `一次性 prompt 派发，devin 没有 goal 模式，每轮结束即停；未完成的 lane 由监督循环按
  .dispatch/progress.md 定点续跑（nudge 驱动，类 opencode）`;
- quota — all lanes share **one Devin org's ACU quota**; the composer shows `Pro · N% remaining
  (resets in Xh)` and exhaustion parks every lane at once (`Quota exhausted` / `Usage limit
  reached`, §6d). Parallel lanes burn ACU in parallel.

**Then verify readiness yourself — `agent start` returning `agent_started` with
`agent_status: idle` and `interactive_ready: true` does NOT by itself prove the composer is up.**
herdr reports the devin session id immediately at start (verified — the herdr hook in devin's
config reports it; record it as the lane's `session` in the state file), but poll the pane:

    herdr agent read <lane> --source visible

Ready means the version banner and the composer placeholder `Ask Devin to build features` are
visible. Two things can block instead:

- A **workspace-trust dialog** — devin trusts directories before running in them. On a machine
  where the worktree's path is not already trusted (verified: no dialog appears when the parent is
  trusted), devin asks before showing the composer. The worktree is a directory this run created, so
  trusting it is inside the run's blast radius: approve the trust-this-directory option with
  `send-keys` (it is a selection list; §6g's digit choreography applies), then re-read until the
  composer is visible. Never trust anything beyond the lane's own checkout path.
- A **login prompt** → the devin account is logged out. Stop the lane and tell the user to run
  `devin auth`; never drive a login flow from the sweep.

On `agent_not_ready` the name still resolves — read, resolve the dialog, continue.

**Then prime** — one prompt, only after the composer is visible. Devin has no goal mode and no
thread-persistent objective, so this one-shot prompt is all the lane has; the sweep's nudges are
the continuation mechanism (§6c):

    herdr agent prompt <lane> "Read .dispatch/TASK.md in this directory and work through its checklist. Keep .dispatch/progress.md updated after every item. Write .dispatch/DONE when everything is finished and verified, then run the notify-back command TASK.md gives you."

Verified end to end: from this one prompt devin reads the brief, executes the checklist, commits,
maintains `progress.md`, writes `.dispatch/DONE` and runs the notify-back, all without a single
approval overlay under `--permission-mode dangerous`.

Record the lane as phase `implementing` with its session id in the state file. One timing trap
(verified): the session row in `sessions.db` does **not** exist until the lane's first prompt —
`agent start` reports the id immediately, but the §6a probe finds no rows until the priming prompt
lands. Probe `unavailable` with reason `no session row yet` in that gap, never `failed`.

Start every lane before supervising any of them.

---

## §6a Probe one lane — write the lane-state helper once

If `~/.claude/dispatch-devin/bin/lane_state.py` is absent, write it, then call
`python3 ~/.claude/dispatch-devin/bin/lane_state.py <session-id>`. One python3 call instead of a
shell pipeline, because Bash permission rules match per shell-operator segment.

Get the session id straight from herdr — `herdr agent get <lane> | jq -r '.result.agent.agent_session.value'`
— devin session ids are slug pairs like `equal-bronze`. Record it in the state file; it also enables
`devin -r <id>` for a manual resume (devin prints this hint on exit, verified). An O(1) cross-check
exists when identity is ever in doubt: `devin list --format json` run **in the lane's checkout**
lists exactly the sessions whose `working_directory` is that checkout (verified).

The helper opens `~/.local/share/devin/cli/sessions.db` **read-only** (it is a live WAL database
shared by every devin session on the machine — `mode=ro` URI, and never write to it) and reports
the probe contract's fields from the lane's own rows:

- `turn_state` — from `message_nodes` for the session, ordered by `node_id`: `complete` when the
  last `assistant` node's `tool_calls` is empty (a final answer ends the turn), `working` when it
  carries tool calls or a `tool` node trails it (verified shape: mid-work the tail is assistant
  nodes with tool calls interleaved with `tool` nodes; a finished turn's tail is an assistant node
  with content and no tool calls). Keep the raw last-node role too.
- `used_pct` — **null**. Devin publishes no context window on disk. The composer shows
  `Context: 37k / 262k tokens` (verified on screen for `swe-2-max`), but §6b forbids pane reads in a
  normal sweep and the window size is model-dependent and server-side, so the sweep does not guess a
  denominator.
- `context_tokens` (devin-only, informational) — the last `assistant` node's
  `metadata.num_tokens_preceding`: the running context size in absolute tokens (verified growing
  37k→42k across one lane's turns). Reported in §6i/§8 in place of a percentage.
- `compactions` — count of the session's `message_nodes` whose `metadata.summarized_from` is not
  null (the compaction-summary marker). Devin compacts automatically in the background; this count
  is observational only — there is no compaction to schedule (§6h).
- `mtime` — the session row's `last_activity_at` (unix seconds), for stall detection. Verified to
  track actual work.
- `model` / `agent_mode` — from the session row (`swe-2-max`, `bypass` at verification time), one
  report line in §8.
- `quota_note` (devin-only) — not from the db: the lane's quota state is screen-only (§6d reads it
  when a lane parks). Always null here.

---

## §6c Classify each lane, in this order

| Class | Test | Action |
| --- | --- | --- |
| `terminal` | phase is `published`, `failed`, user-paused, or `verified` with a recorded §6f degrade reason | Skip — report only; never re-verify, re-publish, or prompt a closed lane |
| `unpublished` | phase is `verified`, `publish_attempts` < 3, no recorded degrade reason, and `pushed_sha` is missing or behind the branch HEAD, or `pr_url` is missing with PRs enabled | Retry publish (§6f) — the work is done, only publishing is left |
| `done` | `.dispatch/DONE` exists **and** `turn_state == complete` | Verify (§6e), publish (§6f), mark terminal |
| `blocked` | `agent_status == blocked` | Read `--source visible`, handle (§6g) |
| `stalled` | `state_change_seq` **and** `mtime` both unchanged ≥ 15 min | Read `--source visible` once: a parked selection list → §6g; quota wording → §6d; an idle composer over unfinished work → the `idle_incomplete` action; otherwise escalate; never score as finished |
| `idle_incomplete` | `done`/`idle`, no `DONE` file | Read `progress.md`, send a specific continuation prompt, record the nudge; a re-nudge with no progress since the last one escalates instead. **This row is the engine** — devin stops after every turn by design |
| `working` | otherwise | Leave it alone |

An `unknown` `agent_status` is an anomaly to surface, never a completion — do not let it fall
through to `working`'s leave-it-alone.

Row-order rationale and the traps behind it:

- **A parked permission selection list reads `done`** (verified) — so `idle_incomplete` fires on a
  lane that is actually waiting for an approval click. This is safe only because of §6b's prompt
  guard: the sweep reads the pane immediately before sending anything, sees the list, and routes to
  §6g instead of prompting. Never drop that guard for this driver.
- `done` sits above `idle_incomplete` and requires `turn_state == complete` because of one verified
  race: a lane's notify-back fires right after DONE is written, mid-turn, so the ringing lane can
  still read `working` with DONE present — re-check it once at the end of the sweep, or leave it to
  the next tick; both are fine.
- There is no `hot` row and no goal rows: nothing schedules a compaction (§6h) and there is no goal
  state to steer (§6d handles quota and drift only).

---

## §6d Steer a parked or drifting lane

All input below goes through `herdr agent prompt <lane> "…"` and is subject to §6b's prompt guard.

**Quota parked → escalate, never nudge in a loop.** When a stopped lane's pane (read once, from
`stalled` or the prompt guard) shows `Quota exhausted`, `Usage limit reached`,
`Organization usage limit reached`, or `Usage paused`: the org's ACU window is empty and every lane
shares it (§5c warned about this). Do not send continuation prompts — they either bounce off the
limit or burn the user's paid on-demand balance without asking. Record `escalated` with the quoted
wording, report the lane as quota-parked awaiting-user, and resume nudging only when the user says
the quota is back (the composer shows `Pro · N% remaining (resets in Xh)` with the reset time).

**`Turn limit reached` / `Response truncated` → nudge normally.** Devin caps a single prompt's
iterations and its max output tokens; both stop the lane with the on-screen instruction `Send a
message to continue`. The lane lands in `idle_incomplete` (stopped, no DONE) and the ordinary
continuation prompt *is* the documented recovery — no special handling, but quote which one fired
in the nudge record so §8 can report it.

**Drift inside the plan vs outside it.** Read `.dispatch/progress.md` before steering. If the lane
is stuck on something the §3-confirmed plan already decides (a misread step, a skipped criterion),
send the corrective prompt with `--wait --until idle --timeout 120000` so its turn actually ends.
If the blocker is real and outside the plan's scope (a missing secret, a broken upstream, a
contradiction in the task itself), escalate with the blocker quoted (record `escalated`); do not
improvise scope.

**A parked selection list found on screen** — resolve it by §6g's rules with `send-keys` only. A
prompt submitted at a parked list presses its highlighted default (verified: a bare digit selects
*and confirms*; assume a full prompt does worse), and devin's default is option 1, `Approve once` —
an approval you did not review.

---

## §6g Handle a blocked lane

Under the default `--permission-mode dangerous` devin raises no approval overlays, so a `blocked`
lane there is an anomaly — usually a trust dialog (§5c) or a herdr misclassification. Read the pane
before assuming which. The rules below apply in full under `--no-yolo`.

Read with `--source visible`. Devin's permission prompt is a **numbered selection list** (verified):

```
❭ 1 Yes  (Approve once)
· 2 Yes, allow `<cmd>` commands
· 3 Yes, always allow `<cmd>` commands in `<dir>`
· 4 Yes, always allow `<cmd>` commands in all projects
· 5 Yes, switch to bypass mode
· 6 Edit command
· 7 Describe change to command
· 8 No
↑↓ select · ↵ confirm · esc cancel
```

Choreography (verified): **a bare digit selects and confirms in one keystroke** — `herdr agent
send-keys <lane> 1` approves once; `esc` cancels (denies). A submitted *prompt* at this list presses
the highlighted default, which is why §6b's prompt guard is load-bearing.

- Benign and inside the lane's own checkout (edit its files, run its tests, read files) → approve
  with `send-keys 1` (**option 1 only**). Options 2–4 widen the permission beyond this one action,
  and option 5 flips the whole lane to bypass mode — under `--no-yolo` that silently changes the
  posture the plan summary promised the user, so 2–5 are never the sweep's to pick. If the lane
  keeps re-prompting for the same class of action, that is a `--no-yolo` cost to surface in §8, not
  a reason to pick a wider option.
- The one sanctioned exception to the bullet below: under `--no-yolo` a finishing lane's notify-back
  (§5b) surfaces *here*, as a permission prompt. If the quoted command is **exactly** the notify-back
  — `herdr agent prompt` aimed at the recorded `orchestrator_pane`, carrying this run's id and the
  lane's own name, with nothing chained after it — approve it with `1`: you briefed it, and the sweep
  reading this overlay is already the sweep it was trying to summon. Any variation — another pane,
  another run id, an extra `;`/`&&` command — is not the notify-back and falls through to the rule
  below. This also means that under `--no-yolo` the doorbell rings late by design, one more cost of
  `--no-yolo`, not a malfunction.
- Anything leaving the lane's blast radius — `git push`, `gh pr create`, force operations, `sudo`,
  deleting outside the checkout, reading credentials, writing to a network target → **do not answer**.
  Deny with `esc`, pause the lane, record it, surface it to the user. Publishing being a normal part
  of this run (§6f) does not make it approvable *here*: §6f runs after verification, on your side of
  the fence. A lane asking to push is a lane that misread its brief.

`herdr agent prompt` returns `agent_blocked` while a dialog is up, so clear it with `send-keys`
first.

---

## §6h No compaction management — and the restart recipe

**Compactions are not the sweep's job here.** Devin compacts automatically in the background
(`compaction_threshold_tokens` in the user's config, a `PostCompaction` hook, and a built-in
fallback to uncompacted history on compaction failure — all present in 3000.10.27; automatic
compaction itself not exercised end-to-end at verification time, take the mechanism as documented).
There is no `/compact`-style command to send and no context window on disk to schedule one against,
so this driver has no `hot` row and no compaction choreography. The §6a `compactions` count is
reported for visibility only. If a lane degrades after many automatic compactions, that is a
restart decision (below), made by you and recorded — never a prompt telling devin to compact.

**The restart recipe — a wedged lane whose pane is still alive.** For a lane that stops responding
(frozen `mtime`, no turn progress across sweeps, escalation already recorded), restart from verified
steps only:

1. Record `restarting: true` on the lane and rewrite the state file.
2. `herdr agent send-keys <lane> ctrl+c` **twice**, a second apart — verified to exit devin cleanly
   from the composer back to the shell prompt (devin prints
   `Resume this session with devin -r <id>` on the way out). Confirm the shell prompt with one
   `herdr agent read <lane> --source visible`.
3. Relaunch exactly per §5c (`agent start` + readiness read), then re-prime with §5c's exact
   one-shot prompt — `.dispatch/TASK.md` and `progress.md` carry the lane's state across the
   restart; that is what they are for.
4. `agent start` returns the **new** session id immediately (verified) — record it at once and clear
   `restarting`. The §6a probe's `no session row yet` gap (§5c) applies again until the re-priming
   prompt lands.

Do **not** try to resume the old session (`devin -r <id>`): its context is the thing being
abandoned, and a resumed thread re-imports whatever wedged it. If the pane does not return to a
shell after the two `ctrl+c`s, the devin process itself is gone or wedged harder than input can
reach: escalate to the user; never `worktree remove` (§0.5).

Devin has a `/clear` command (starts a fresh conversation in the same process) — present in
3000.10.27 but **unverified** under `herdr agent prompt`; the ctrl+c/relaunch path above is built
from verified steps only, so it is the recipe. If `/clear` is ever adopted later, re-verify that the
session id changes and when herdr reports the new one before trusting it in a sweep.
