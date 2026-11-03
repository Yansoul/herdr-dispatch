# omp driver — §5a, §5c, §6a, §6c, §6d, §6g, §6h

All presets use this driver. With omp 18.15.0, Herdr launch through local magpie, goal completion,
exact-file restore, and scout/sonic child inference through a run-scoped overlay were exercised.
Read installed CLI help on version changes; never apply native Codex/Cursor/Devin commands to omp.

## §5a Preflight

Follow routing.md before creating lanes. In each lane's shell run `omp --version` and read the visible output; a resolving shim alone proves nothing. Install the repository's required dependencies before starting the agent. Obtain authorization before linking missing secrets; never copy them. Write TASK.md (§5b) before launch.

Prepare a unique empty `<run-dir>/<lane>-sessions/` and record its absolute path as `session_directory`; do not share it between lanes. Create the routing overlay from routing.md. To enumerate bundled agent names without changing installed agents, use `omp agents unpack --dir <run-dir>/bundled-agents --json`, then inspect frontmatter plus discovered user/project agent definitions. Pin every discovered agent model in the overlay. These exported files are inspection artifacts, not new active agents.

Record `schema_version: 2`, `agent_kind: "omp"`, omp version, per-lane `model`, `thinking`, `role_models`, `runtime_config`, `session_directory`, `approval_mode`, and `launch_state: "prepared"`. Keep session id/path null until observed. Shell-quote every argument, including paths and goals; never concatenate untrusted task text into a shell program.

## §5c Launch and goal

Use the existing recorded shell pane, not omp's own worktree feature:

```text
herdr agent start <lane> --kind omp --pane <pane> --timeout 120000 -- \
  --config <runtime_config> --model <model> \
  --smol <model> --slow <model> --plan <model> --thinking <thinking> \
  --no-prewalk --no-title --no-extensions \
  --session-dir <session_directory> --approval-mode <approval_mode> \
  --goal "Read .dispatch/TASK.md and execute its plan. Keep .dispatch/progress.md current. Verify all acceptance criteria, commit the work, write .dispatch/DONE, and run the exact notify-back command in TASK.md. Then complete the goal."
```

`approval_mode` is `yolo` by default, `always-ask` under --no-yolo; never inherit an unknown global approval posture. Explain that neither is a sandbox. `--no-extensions` avoids unreviewed model-routing hooks; preserve skills and project instructions. If a reviewed integration extension is necessary, explicitly load only that extension with `-e <path>` and record it. Do not disable rules or context files in real lanes.

`--goal` starts a **fresh** interactive session and is incompatible with positional prompts or explicit resume. Do not send another initial prompt: it would duplicate the goal. Record `launch_state: "starting"` before the command, then inspect both the visible pane and the session metadata. Require the recorded model and an active/complete goal. `agent_started` or `idle` alone is not proof of a successful turn. If launch times out, inspect the existing pane before retrying; never spawn a duplicate. A startup approval blocks the goal until handled (§6g).

Once the session header/path are established, record them and set phase `implementing`, launch_state `running`. Start the other lanes, then supervise. If the first turn has a provider/auth/unknown-model error, record the route failure; do not repeatedly restart or switch models. A missing route stops only affected lanes.

Tell the user: `所有 lane 使用 omp，模型经 magpie 路由；每个 lane 固定路由和 thinking。默认 yolo / --no-yolo 为 always-ask，均不是沙箱。omp goal 持续执行，监督循环负责验收和恢复。`

## §6a Probe from disk

Session identity is separate from model routing. The session header is:

```json
{"type":"session","version":3,"id":"...","cwd":"..."}
```

With no integration extension, Herdr may expose no agent_session. On first launch, accept exactly one top-level `*.jsonl` in the previously empty recorded session_directory whose header cwd canonicalizes to the lane checkout and has no parentSession. Record its absolute `session_file` and header `session` id. Never select the newest file from a global directory. On every sweep verify the header, canonical cwd, recorded pane and runtime kind. If Herdr supplies `agent_session`, record its representation as `session_identity` and check it too; the local integration reports a file path rather than the header UUID. Any unexpected path/id change is an ownership failure. Multiple candidate sessions require diagnosis, not guessing.

Read records incrementally with a stored byte offset, retaining the latest metadata in state. On first attachment stream the file once without loading it all into memory or printing message bodies. Ignore an unfinished final JSONL line and retry it next sweep; file shrink/replacement invalidates the cursor and identity must be rechecked. omp entries have id/parentId; a branch switch invalidates a simple latest-record interpretation. Follow the active parent chain, or report unavailable until reattached; never steer from stale branch state.

Extract only these fields:

- `model_change.model`: full selector. Require the recorded magpie route. Inspect `model_usage` provider/model fields when available, including child session metadata. Do not mistake token totals or a title for model identity.
- `mode_change.data.goal`: goal snapshot, including `id`, `status`, `tokensUsed`, `timeUsedSeconds`. Observed status values include `active`, `paused`, `complete`. Completion is followed by `mode_change` with mode `none`; retain the last goal snapshot for diagnosis but do not treat it as a currently active goal. Unknown modes/statuses stay unknown.
- `message.message`: role and stopReason only, plus usage when available. A successful final assistant reply is corroboration of a finished turn; tool calls/tool results are intermediate. Errors/aborts are not successful completion. Reconcile with Herdr working/blocked state and goal transitions. When a hook is absent or live activity cannot be established, use `turn_state: "unknown"` rather than inferring idle from silence.
- `compaction`: count observed entries, retain tokensBefore/tokensAfter for diagnostics. These are snapshots, not current utilization. `used_pct: null` unless an authoritative live context measurement is available; never use cumulative goal tokens as context use.
- `mtime`, last observed metadata change, `.dispatch/progress.md` mtime, and DONE existence. Retain two consecutive sweeps for stall detection.

Return `probe: ok|unavailable` with reason, `session`, `turn_state: working|complete|unknown`, `used_pct`, `compactions`, `mtime`, `goal_status`, `goal_mode`, `model`, `route_error`. Missing/corrupt files mean unavailable, never finished. No external provider requests are made by a probe.

## §6c Classify (first matching row)

| Condition | Action |
| --- | --- |
| terminal/escalated/user-paused lane | report only; cleanup only per shared contract |
| legacy schema, identity or route mismatch | stop steering, record escalation |
| phase verified, not yet published | §6f; honor recorded failure/degrade reason |
| phase published | §6j unless opted out |
| agent absent from recorded pane | §6h restore only after proving shell and session ownership |
| known provider/auth/quota failure | §6d; no fallback to another runtime/provider |
| blocked/modal | §6g |
| agent working or disk activity advancing | leave running, even if DONE exists |
| DONE exists, agent settled, no active work | §6e independently verify |
| goal complete but no DONE | §6d ask it to reconcile TASK.md; goal completion alone is insufficient |
| paused goal | do not override a user pause; record awaiting-user unless pause is clearly a recoverable runtime condition |
| active goal with settled/no-progress readings across two sweeps | §6d diagnose visible pane once; do not interrupt merely between goal turns |
| goal inactive, settled, checklist incomplete | §6d continuation |
| unavailable/unknown | inspect visible pane once; if still uncertain escalate rather than type blindly |

## §6d Steer

Before every input, prove identity and read the visible pane (§6b guard). Never prompt an active turn or selection menu. When settled but incomplete, send one ordinary prompt to read TASK.md/progress.md, finish remaining criteria and re-enter/resume its goal using omp's goal tool if needed. Do not use Codex's `/goal resume` syntax. If a continuation fails to advance across the next sweep, record escalation rather than a prompt loop.

A gateway outage is checked with `magpie healthcheck`; after it recovers, a settled failed turn can receive one continuation using the same recorded route. Authentication, missing subscription and persistent provider errors require a reported blocker. Never log keys, change global routing, or restart all lanes for one route failure. Record last error and recovery attempt so each sweep does not repeat it.

## §6g Approvals and questions

`always-ask` may park at a tool approval. Read the visible prompt and approve only operations already authorized in this lane's TASK.md, confined to the lane's checkout. Do not assume key bindings: inspect the actual UI. Decline/escalate requests to publish, modify other lanes, change credentials or expand scope. A yolo lane can still ask a question; do not dismiss it blindly. Tell the user the concrete blocker when their input is necessary.

## §6h Context maintenance and recovery

omp automatic compaction is enabled by the overlay; no dispatcher token threshold or periodic `/compact` is needed. Observe compaction records. Do not reset a healthy goal or send native-agent slash commands to fix context pressure. If context maintenance fails repeatedly, record the failure and escalate; never silently discard history.

When the process has exited, verify the recorded pane is back at an idle shell, the session header/cwd still match, magpie is healthy and the saved route exists. Persist `launch_state: "restoring"` before relaunch. Use the §5c launch command with **the same overlay/model/roles/thinking/approval/session directory**, but replace `--goal ...` with `--restore <absolute-session_file>`. Never combine --goal and --restore, never use --continue or pick a session by cwd. Restore resumes interrupted work and its subagents; for an already settled session, send one guarded continuation only if TASK.md remains incomplete. If work finished, verify instead.

If a process is hung rather than exited, do not start a second one. Inspect its visible state, preserve progress, and report the blocker. If the recorded session is lost/corrupt, a fresh goal requires an explicitly recorded recovery decision based on TASK.md/progress and repository state; preserve the old file, never claim history was restored. A resumed process must report the same session header id/path before receiving steering.
