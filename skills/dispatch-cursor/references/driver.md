# Cursor driver — §5a, §5c, §6a, §6c, §6d, §6g, §6h

Everything in `dispatch-cursor` that depends on cursor itself. The agent-independent halves are
`references/plan.md` (§2–§4, §5b) and `references/supervise.md` (§6b, §6e, §6f, §6i, §7, §8);
§0 and §1 are in `../SKILL.md`.

Sources for the claims below: `cursor-agent --help` (the binary reports its usage as `agent`), the
slash-command registry and goal skill bundled in the installed CLI
(`~/.cursor/skills-cursor/goal/SKILL.md`), and live sessions driven through herdr on this machine.
Claims marked **(verified)** were exercised end-to-end against cursor-agent **2026.09.10-fd3934a**
inside herdr 0.9.0 panes; **(observed)** means read off real on-disk state; **(unverified)** has not
been exercised — handle its failure path, never assume it works. §2 records the version it actually
finds; a mismatch is a report line, not an abort. Cursor ships fast, and more of its behaviour lives
in the binary than in documentation.

---

## §5a Pre-flight the pane

A fresh worktree is not a working environment: no `node_modules/`, no `.env`, no `.venv`, because
those are untracked or ignored.

    herdr pane run <pane> "cursor-agent --version"

Run the version, not `command -v`: a shim can resolve while the real binary does not, and then
`agent start` just times out. The executable herdr launches for `--kind cursor` is `cursor-agent`;
its usage banner calls itself `agent`, and some machines alias `agent` to a different CLI entirely —
that alias is irrelevant here, because `agent start` resolves `cursor-agent` from the pane's own
login shell and args cannot redirect it.

Then poll `herdr pane read <pane> --source visible`. Two verified CLI traps here: `herdr pane read`
with **no `--source`** returns empty output with exit code 0, and `herdr pane wait-output` only
matches output arriving *after* the call, so it times out on a command that already finished. Poll
`--source visible` instead of waiting.

- `cursor-agent` not found, or the version refuses to resolve → stop that lane and report it.
- Dependencies missing → run the repo's install command in the pane and let it finish **before**
  starting the agent; `agent start` needs a pane at an idle interactive prompt.
- `.env` or other secrets missing → **ask the user** whether to symlink them. Never copy secrets.
- Login: if the pane shows a sign-in prompt instead of a composer after launch, stop the lane and
  tell the user to run `cursor-agent login` themselves — authentication is theirs, never the run's.

Then write the brief (§5b in `references/plan.md`) before launching.

---

## §5c Launch cursor and set the goal

Launch with **no positional prompt**. Cursor accepts one, but a goal is set by slash command, which
cannot ride along on argv, and priming through `herdr agent prompt` is what lets you verify the
composer is actually accepting input first — a startup modal eats whatever reaches it.

    herdr agent start <lane> --kind cursor --pane <pane> --timeout 120000 -- --force --trust

Why each part:

- `--force` ("Run Everything", aliased `--yolo`) is **on by default**: lanes run unattended and an
  approval overlay stalls a lane until the next sweep notices it. The status line's right edge reads
  `Run Everything` when it is in force (observed), and the chat's meta records
  `approvalMode: "unrestricted"` (§6a cross-checks it). Under `--no-yolo`, drop it; the lane then
  prompts per tool call and §6g handles every overlay. Pass nothing in its place — cursor's
  approvals are opt-out via this flag, so omission *is* the normal-posture signal.
- `--force` is **not** a sandbox. Cursor has a separate `--sandbox enabled|disabled` (and a
  `/sandbox` menu whose setting persists across sessions). This skill does not touch it: whatever
  the user configured stays in force. If sandboxing is off, say so in §3's first line rather than
  implying an isolation that is not there — the worktree is then the only boundary.
- `--trust` skips the workspace-trust dialog in interactive mode — **verified on this build**, even
  though older forum reports claimed it was headless-only. Every fresh worktree is an untrusted
  directory, so without it every lane would park at launch. It is not an approval bypass — it only
  answers "do you trust this directory" — so pass it under `--no-yolo` too.
- `--timeout 120000` because a cold start plus MCP boot can far exceed herdr's 30 s default.
- Never pass `-w` / `--worktree`: cursor would create a *second* worktree of its own under
  `~/.cursor/worktrees/`, and the lane would then be committing somewhere §6e never looks and §6f
  never pushes (§4).
- Never pass `-p` / `--print`, `--output-format`, or `--stream-partial-output`: those are headless
  modes, and this skill needs a live TUI that herdr can read and prompt.
- No `--resume` / `--continue`: each lane is a new chat, and §6a identifies it by directory.
- `--approve-mcps` is deliberately **not** passed: an MCP the user has not approved surfacing as a
  prompt is a signal worth seeing (§6g), not something to blanket-approve.

**The three lines §3 owes the user, in this driver's words:**

- approval posture — `yolo（--force，Run Everything：工具调用不再询问；沙箱配置原样保留）` by default,
  or `--no-yolo（工具调用在 pane 里弹权限提示，由监督循环处理，lane 会因此停顿到下一轮 sweep）`;
- how the lane is driven — `以 cursor goal 模式运行（/goal 持久目标）：按上面的实施计划执行、以验收标准为
  完成判据，跨轮次自动续跑，cursor 自认完成前会逐条核对证据`;
- rate limits — all lanes share one Cursor account, so its usage window is shared and can throttle
  every lane at once; `/usage` in the pane is where the numbers are.

**Then verify readiness yourself — `agent start` returning `agent_started` with
`agent_status: idle` and `interactive_ready: true` does NOT mean cursor is ready.** On an untrusted
directory without `--trust`, cursor shows a boxed modal titled `⚠ Workspace Trust Required` asking
`Do you trust the contents of this directory?` with options `[a] Trust this workspace` / `[q] Quit`
— and herdr still reports the agent started and idle (verified). Read the pane:

    herdr agent read <lane> --source visible

If it matches `Workspace Trust Required`, send `herdr agent send-keys <lane> a` once (verified: `a`
selects and confirms trust), then re-read until the composer (`→ Plan, search, build anything`) is
visible. Only then is the lane ready for input. On `agent_not_ready` the name still resolves —
read, resolve the dialog, continue.

**Then set the goal** — one call, and only after the composer is visible:

    herdr agent prompt <lane> "/goal Work through .dispatch/TASK.md in this directory: follow its plan in order, satisfy every acceptance criterion, keep .dispatch/progress.md updated after every checklist item, and finish by writing .dispatch/DONE and running the notify-back command TASK.md gives you."

Verified on this build: the slash command executes (never lands as literal text), cursor calls its
`CreateGoal` tool with the objective, the status row's right edge reads `Goal active (Ns)` with a
running clock, and pursuit auto-continues across turns. Completion is cursor's own
`UpdateGoal status=complete` plus a `Goal complete` line — and cursor's bundled goal skill requires
an evidence audit against current state before that call, which complements (never replaces) §6e.

What a goal buys over a plain prompt, and what it changes for supervision:

- The objective is **durable across turns**: cursor continues toward it instead of stopping for
  input, so an unfinished lane picks *itself* up — nudge prompts are a repair path (§6c
  `idle_incomplete`), not the engine. This is the **autonomous** regime
  `references/supervise.md` §7 refers to.
- Goal state lives in cursor's conversation state, which §6a does not decode; what §6a *can* read
  is the goal's **tool trail** (`CreateGoal` / `UpdateGoal` calls are plaintext inside the store's
  blobs, observed) — enough to tell `active` from `complete`. Cursor's goal skill documents no
  `status` / `pause` / `resume` verbs and no budgets: "a goal continues until it is complete."
  Steering is by ordinary prompts (§6d), not goal subcommands.
- **Prompts sent mid-turn queue as follow-ups** (verified): the composer shows a `follow-ups` box
  (`enter steer · ↑ select/edit · esc cancel`) and the queued text fires when the in-flight turn
  ends. Slash commands are not refused the way codex refuses them — but a queued `/goal` arriving
  while a goal is still active is exactly the double-fire case, so §6d still gates on the prompt
  guard and the goal trail.
- **No replace-goal dialog was observed** (verified for one ordering: a second `/goal <objective>`
  sent during goal A's pursuit queued as a follow-up and, firing after A completed, started goal B
  with no dialog). A second `/goal` reaching a *still-active* goal is untested — the skill says
  `CreateGoal` exactly once, so send one `/goal` per lane per thread and no more (§6h's restart
  re-sets one dialog-free, on a fresh thread).

Record the lane as phase `implementing` with its chat uuid (from `agent_session.value`, §6a) in the
state file. If `/goal` lands as literal text or draws an unknown-command response, record
`goal_skipped` with the reason, surface it in §8, and fall back to the one-shot prompt — same
objective, no auto-continuation, so the sweep's nudges are all it has:

    herdr agent prompt <lane> "Read .dispatch/TASK.md in this directory and work through its checklist. Keep .dispatch/progress.md updated after every item. Write .dispatch/DONE when everything is finished and verified, then run the notify-back command TASK.md gives you."

Start every lane before supervising any of them.

---

## §6a Probe one lane — write the lane-state helper once

If `~/.claude/dispatch-cursor/bin/lane_state.py` is absent, write it, then call
`python3 ~/.claude/dispatch-cursor/bin/lane_state.py <checkout>`. One python3 call instead of a
shell pipeline, because Bash permission rules match per shell-operator segment. Python's stdlib
`sqlite3` is enough.

**Finding the lane's chat.** At dispatch time, take the uuid straight from herdr —
`herdr agent get <lane> | jq -r '.result.agent.agent_session.value'` — verified to equal the chat
directory name under `~/.cursor/chats/<hash>/<chat-uuid>/`. That is the O(1) lookup; record the
uuid in the state file. **After any §6h `/clear`, that uuid is dead**: herdr keeps reporting the
pre-clear one even after the fresh thread's first turn completes (verified), so re-identify from
disk instead — scan `~/.cursor/chats/*/*/meta.json` for `cwd` equal to the lane's checkout, newest
`updatedAtMs` first, and require the winner's uuid to **differ** from the recorded one before
writing it back. Never reconstruct the `<hash>` level; the `meta.json` scan survives whatever it
encodes. A `store.db` is written on first activity, so a just-cleared lane may briefly have an empty
new directory — that is normal, not an anomaly.

**Reading `store.db`.** Open it as `file:<path>?mode=ro` — read-only, **not** `immutable` (§0.3).
Schema (observed): `blobs(id TEXT PRIMARY KEY, data BLOB)` plus `meta`. The `meta` value is a
hex-encoded JSON object (observed keys: `agentId`, `name`, `mode`, `isRunEverything`,
`approvalMode`, `createdAt`, `lastUsedModel`, `blobEncryptionKey`). Inside `blobs`, two payload
kinds coexist (observed): plaintext JSON messages (`{"role":"user"|"assistant", "content":…}`) and
**protobuf envelopes** whose readable strings embed an assistant message as a JSON substring
(`{"id":"msg_…","role":"assistant",…}`) alongside file paths and tool records. Parse both
defensively; a blob that matches neither shape is not an error, it is a skip.

The helper reports the probe contract's fields:

- `session` — the chat uuid as recorded/re-identified above.
- `turn_state` — from herdr: `agent_status == working` → `working`; `done` / `idle` → `complete`;
  anything else → `unknown`. Cursor's on-disk turn boundary is **(unverified)** — the envelopes
  carry timestamps but no verified finish marker — so herdr's status is the turn signal here, with
  `mtime` as the honesty check: a `complete` whose `mtime` is still advancing is a turn in flight.
- `used_pct` — **always `null`**. Cursor publishes no context window on disk, and the only
  percentage lives in the TUI status line (`Cursor Grok 4.6 Extra High · 13.3%`, observed — read as
  "used", but its exact definition is unverified and §6b forbids pane reads in a normal sweep).
  Report `null` rather than inventing a denominator (§1).
- `compactions` — count of summary markers in `blobs` (observed from a real `/summarize`): a user
  message whose text starts `[Previous conversation summary]:`, or a blob whose text begins
  `Summary:` with sections like `Primary Request and Intent`. Cursor may also summarize on its own
  (a `summarized_conversation` category exists in its context-breakdown blobs, observed) — the same
  markers count either origin.
- `mtime` — `store.db`'s modification time, for stall detection.
- `probe` — `ok` / `unavailable` with a reason (no chat dir matches the checkout, or the schema
  moved). A probe that admits it is blind beats one that guesses (§0.3).
- `goal_trail` (cursor-only) — scan the blobs for goal tool records (observed plaintext inside the
  protobuf envelopes: `"tool": "CreateGoal"` and `"tool": "UpdateGoal"`). Report `active` when a
  `CreateGoal` exists with no later `UpdateGoal` carrying a terminal status, `complete` when one
  does, `none` when no goal was ever created. This is inferred from the tool trail, not decoded from
  cursor's conversation-state `goalState` — its format is unverified. Treat `UpdateGoal` statuses
  beyond `complete` as opaque strings and report them raw.
- report-only extras from `meta`: `name` (cursor auto-titles chats — a title with nothing to do with
  the lane's objective is an early sign the lane misread its brief), `isRunEverything` /
  `approvalMode` (cross-check against the run's recorded yolo posture; `unrestricted` under
  `--force`, observed), `lastUsedModel`.

`/usage` answers on screen only; there is no verified shell-level usage query for cursor, so §8 gets
its usage picture from `compactions`, `mtime` history and the goal trail, not token totals.

---

## §6c Classify each lane, in this order

| Class | Test | Action |
| --- | --- | --- |
| `terminal` | phase is `published`, `failed`, user-paused, or `verified` with a recorded §6f degrade reason | Skip — report only; never re-verify, re-publish, or prompt a closed lane |
| `unpublished` | phase is `verified`, `publish_attempts` < 3, no recorded degrade reason, and `pushed_sha` is missing or behind the branch HEAD, or `pr_url` is missing with PRs enabled | Retry publish (§6f) |
| `done` | `.dispatch/DONE` exists **and** `turn_state == complete` | Verify (§6e), publish (§6f), mark terminal |
| `blocked` | `agent_status == blocked` | Read `--source visible`, handle (§6g) |
| `blind` | `probe == unavailable` for two consecutive sweeps | The store is not answering for this lane. Read `--source visible` once, judge from git state, and escalate rather than steering a lane you cannot see |
| `identity_mismatch` | the recorded uuid's `meta.json` `cwd` ≠ the lane's checkout, or the newest chat for this checkout changed with no restart in flight | Surface it; steer nothing (§6b) |
| `over_summarized` | `compactions ≥ 3` and the lane is not terminal | Repeated summarization degrades accuracy — restart per §6h instead of summarizing again |
| `stalled` | `state_change_seq` **and** `mtime` both unchanged ≥ 15 min, and `goal_trail` is not `complete` | Read `--source visible` once: a trust modal → §5c's `a`; a parked selection list → §6g; an idle composer over unfinished work → the `idle_incomplete` action; otherwise escalate; never score as finished |
| `idle_incomplete` | `turn_state == complete`, no `DONE` file, **and** `goal_trail` is not `active` | Read `progress.md`, send a specific continuation prompt, record the nudge; a re-nudge with no progress since the last one escalates instead |
| `working` | otherwise | Leave it alone |

An `unknown` `agent_status` is an anomaly to surface, never a completion — do not let it fall
through to `working`'s leave-it-alone.

Row-order rationale: there is no `hot` row — §1 explains why this skill never compacts on a
threshold — and no `goal_parked` row, because cursor's goal pause/limit states are not readable
from disk; a goal lane frozen by either surfaces through `stalled`'s frozen `mtime` instead.
`idle_incomplete` excludes an `active` goal because between auto-continued turns a goal lane briefly
reads `done` — that gap belongs to cursor's continuation. A prompt sent into the gap would queue as
a follow-up (verified) rather than fuse into the composer, so the collision codex fears is milder
here, but the sweep still stays out as a precaution; an `active` goal that is *truly* wedged
surfaces through `stalled`.

One known race, by design: a notify-back can arrive before the ringing lane's final turn closes (the
brief fires it right after DONE is written, mid-turn), so that lane may still read `working` with
DONE present — re-check it once at the end of the sweep, or leave it to the next tick; both are
fine.

---

## §6d Steer a lane

Cursor's goal has no documented `status` / `pause` / `resume` verbs (its bundled skill: "a goal
continues until it is complete"), so steering is by ordinary prompts, and every one of them is
subject to §6b's prompt guard. A prompt sent mid-turn queues as a follow-up and fires at turn end
(verified) — no composer-clearing ritual is known to be needed (the follow-up box offers
`esc cancel`), but if a steering prompt never fires, read the pane and cancel the stale queue entry
before retrying.

**A lane that stopped with its goal still `active`** — the common `idle_incomplete` case worth
nudging. Read `.dispatch/progress.md` and send a continuation prompt that names the next unchecked
checklist item and the file it touches. Whether cursor re-engages the goal on its own after such a
stop is **(unverified)** — check next sweep: `mtime` moved means the lane picked itself up and the
nudge was redundant but harmless; nothing moved means the nudge *is* the engine for this lane from
here on.

**Anti-loop accounting is mandatory** (same rule as the nudge-driven dispatchers). With every nudge
record `nudges`, the branch HEAD sha, and a hash of `progress.md`. Next sweep: a new commit or a
changed `progress.md` resets the no-progress counter; neither increments it. At `no_progress == 1`,
nudge once more, differently — quote the blocker if the pane shows one, or narrow the ask to a
single file. At `no_progress == 2`, **stop nudging**: record `escalated` and report the lane as
awaiting-user. Never fire a third identical nudge.

**`complete` but no `DONE`** — cursor considers the goal met (its audit passed) while the completion
protocol did not finish. The lane reaches `idle_incomplete`; the continuation prompt there is safe:
with no active goal there is no auto-continuation to collide with.

**A goal tool-recorded status beyond `complete`** — anything §6a's `goal_trail` reports raw. The
statuses cursor accepts are undocumented here, so treat any of them as "the model says it cannot
proceed": read `.dispatch/progress.md` and the pane for the blocker. If the answer lies inside the
§3-confirmed plan — a decision the brief already made, a misread step — send the corrective prompt.
If the blocker is real and outside the plan's scope (a missing secret, a broken upstream, a
contradiction in the task itself), escalate with the blocker quoted (record `escalated`); do not
improvise scope.

**Pausing a lane** is a user decision, not a sweep's. Cursor's pause UX for goals is unverified, so
this skill does not send one: record `pause: {origin: user, at: <sweep time>}` and simply stop
steering — a lane nobody nudges and whose goal stopped is a lane at rest. Such a lane is terminal
for §7 until the user says otherwise. A lane found paused or stopped by a hand you cannot see is
treated the same way: escalate once, never resume on your own.

**A second `/goal` must never leave this sweep.** One `/goal` per lane per thread (§5c). No replace
dialog was observed (§5c), but an untested double-fire could still redefine a lane's objective
mid-run — if the state file shows two goal-set events for one thread, that is the bug to fix, not a
situation to steer through.

---

## §6g Handle a blocked lane

Under the default `--force`, cursor raises no approval overlays (the status line reads
`Run Everything`, and the chat meta records `approvalMode: "unrestricted"`, observed) — so a
`blocked` lane there is an anomaly: a trust modal §5c somehow missed, an MCP approval prompt
(`--approve-mcps` was deliberately not passed), a model or settings dialog, or a herdr
misclassification. Read the pane before assuming which. The rules below apply in full under
`--no-yolo`.

Read with `--source visible`. Cursor's permission dialogs and their hotkeys are **(unverified)** in
this driver, so answer only with `send-keys` matching the option actually displayed. Never type a
remembered key, and never send a prompt at a parked list — it presses the highlighted default.

- Benign and inside the lane's own checkout (edit its files, run its tests, read files) → approve the
  narrowest option offered. Prefer a once-only approval over any "always/remember" option: the latter
  outlives this run and changes the user's machine.
- The one sanctioned exception: under `--no-yolo` a finishing lane's notify-back (§5b) surfaces here
  as an approval request. If the quoted command is **exactly** the notify-back — `herdr agent prompt`
  aimed at the recorded `orchestrator_pane`, carrying this run's id and the lane's own name, with
  nothing chained after it — approve it: you briefed it, and the sweep reading this dialog is
  already the sweep it was trying to summon. Any variation — another pane, another run id, an extra
  `;`/`&&` command — is not the notify-back and falls through to the rule below. Under `--no-yolo`
  the doorbell rings late by design.
- Anything leaving the lane's blast radius — `git push`, `gh pr create`, force operations, `sudo`,
  deleting outside the checkout, reading credentials, writing to a network target → **do not
  answer**. Pause the lane (§6d), record it, surface it to the user. Publishing being a normal part
  of this run (§6f) does not make it approvable *here*: §6f runs after verification, on your side of
  the fence. A lane asking to push is a lane that misread its brief.

`herdr agent prompt` returns `agent_blocked` while a dialog is up, so clear it with `send-keys`
first.

---

## §6h Compact a lane

    herdr agent prompt <lane> "/summarize" --wait --until idle --timeout 120000

`/summarize` is cursor's compaction command (verified on this build: executed through
`herdr agent prompt`, wrote a `[Previous conversation summary]:` message and `Summary:` blobs to
`store.db`). Mid-turn it queues as a follow-up and runs at turn end (§5c) — no refusal dance — but
the prompt guard still applies: never send it into a parked selection list.

- **The sweep never summarizes on a threshold** (§1) — there is no disk-readable percentage to gate
  on. `/summarize` is a repair step: run it when §6c's diagnosis calls for shrinking context (a
  stalled lane whose `mtime` froze mid-turn with a long history), never as routine maintenance.
- **Success is an effect, not a return code.** §6a's `compactions` count must increase. If one
  `/summarize` does not raise it, record `compact_unavailable`, stop trying for the rest of the run,
  and use the restart recipe instead — do not retry sweep after sweep.
- **After summarizing a goal lane, do not re-prime by prompt.** The goal lives in conversation
  state, which summarization preserves by design; whether pursuit re-engages on its own is
  **(unverified)** — so check, don't assume: on the next sweep, require `goal_trail` still `active`
  **and** a moving `mtime`; an `active` goal with no new activity after a summary gets one §6d
  continuation prompt, and if that changes nothing, escalate. Only a `goal_skipped` lane gets the
  §5c one-shot prompt text re-sent after a summary.
- **Stop after 3 summarizations** (§6c's `over_summarized` row) and hand off to the restart recipe.

**The restart recipe — a fresh chat on the same pane, for a lane whose own agent is alive.**
The paths that end here are `over_summarized` and a stalled lane that did not recover (a §6b
identity mismatch is *not* one of them — §6b routes each of its cases itself). In order:

1. Record `restarting: true` on the lane and rewrite the state file — this keeps the next sweep from
   firing the same row again off the old chat while the restart is mid-flight.
2. `herdr agent prompt <lane> "/clear"` — verified: the composer returns to a fresh chat. Check
   `progress.md` is current *before* sending; the fresh chat's entire handover is `.dispatch/TASK.md`
   plus that file, and a stale one is an escalation, not a restart.
3. Re-prime exactly as §5c does: a `/goal` call for a goal lane (the fresh chat has no goal, so no
   double-fire is possible), or the §5c one-shot for a `goal_skipped` lane.
4. Re-identify from **disk**, never from herdr: `agent_session.value` keeps reporting the pre-clear
   uuid even after the fresh thread's first turn completes (verified). Poll §6a's `meta.json` scan
   until a chat whose `cwd` matches the checkout appears with a uuid that **differs** from the
   recorded one, then record the new uuid and clear `restarting`. Never write back an id you have
   not seen change on disk — that leaves the sweep reading a dead chat and restarting forever.

If the pane does not respond to `/clear`, the cursor process itself is gone or wedged: escalate to
the user; never `worktree remove` (§0.7), and relaunching via `agent start` needs the pane back at
a shell prompt first (§5a's checks apply again).
