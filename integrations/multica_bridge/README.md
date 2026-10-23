# Multica → Herdr Dispatch Bridge (experimental)

This integration keeps Multica as the task UI and the existing herdr-dispatch as
the execution engine. It is an **experimental, fail-closed adapter**, not a
production-grade exactly-once distributed workflow.

## Requirements

- Python 3.10+ on macOS/Linux, `herdr`, `multica` CLI, Claude Code plugin,
  Git checkout of the repository you want to work in.
- A dedicated user or VM. Herdr lanes may run without sandbox/approval by default.
- Multica CLI authenticated and able to read/write the intended workspace.
- Multica CLI `--help` flags may change with versions. Verify locally before use.
- No separate Multica Agent assignment needed. Do not configure automatic native
  agent execution for bridged issues.

## Configuration

Copy `config.example.json` to `config.json` **outside Git**, set real
workspace ID, project key -> local checkout mappings and allowed approver IDs.
`config.json` must remain private. Make sure `state_dir` is on a durable disk
reachable by the Herdr orchestrator.

## Commands

```bash
python3 integrations/multica_bridge/bridge.py --config /private/bridge.json once
python3 integrations/multica_bridge/bridge.py --config /private/bridge.json run
python3 integrations/multica_bridge/bridge.py --config /private/bridge.json status
python3 integrations/multica_bridge/bridge.py --config /private/bridge.json recover MUL-42
```

## Workflow

1. Create a regular Multica issue in Backlog. Nothing executes on creation.
2. When ready, set **status=todo** and issue metadata **herdr_dispatch=ready**.
   Both are required. Only projects in the configuration are scanned.
3. Controller atomically records a stable job ID, creates a no-focus Herdr
   workspace, starts a Claude orchestrator inside the new pane, and requests
   **planning only**. No source edit is authorized at this stage.
4. Planning agent writes `state_dir/jobs/<job_id>/plan.json` with one or more
   validated lanes, including tasks, plan steps and actual acceptance checks.
5. Bridge publishes a comment containing the *SHA-256* of the plan file and
   sets in-review. Your approval must be a new comment:
   `APPROVE <64-character-sha256>` from an allowlisted Multica account.
6. Bridge writes `approved.json`, sends `--approved-plan` instruction to
   your existing Herdr dispatcher and requests `--no-automerge`.
7. Herdr dispatch independently validates the approved plan; its authoritative
   state must include `bridge_job_id`, `bridge_issue`, and
   `bridge_plan_sha256`.
8. Once every lane is published or merged, the Bridge marks the issue
   in-review, leaving final acceptance to you.

**Important:** The new Skill protocol is an instruction contract implemented
in Markdown, not a compiled command parser. End-to-end approval, dispatch,
and session recovery have **not** yet been exercised against live CLIs.
Do not enable background service startup until completing the smoke test.

## Reliability boundary

The controller uses a single-writer lock and SQLite uniqueness constraints.
Commands that might produce side effects are journaled in `phase` before
execution. In ambiguous outcomes, the controller fails **closed** to
`needs_recovery`; it **never blindly replays** a workspace create, agent
start, or prompt. Multica metadata and issue status are projections, not
evidence of successful execution. Completion ACKs are advisory; only
matching Herdr dispatch state and verified lane phases count as delivery.

**Known first-version gaps:**

- Recovery is inspection-only. `recover` shows the journal and requires
  manual reconciliation; there is no automatic pane recreation or command ACK
  protocol yet.
- Live Multica issue/comment schema, approver author IDs, project selectors
  and CLI compatibility require a smoke test with your installed version.
- The controller currently does not inject a true persistent external timer
  into Herdr's Session supervisor; use the original Skill's supervision loop.
- The bridge does not auto-cancel active workers when a task is closed,
  or auto-merge PRs. Manual intervention is required.
- The bridge does not render native Multica Runs for external Herdr Sessions.
- `in_review`, `blocked`, and `todo` statuses need to exist on the target
  workspace; adapt status mappings to its workflow.
- Multica API failures during status synchronization may recur; no delivery
  ledger for every outbound comment has been implemented beyond plan hash
  markers.
- The bridge does not yet implement automatic resumption of ambiguous dispatch
  sends. **Do not consider this deployable unattended without hardening.**

## Failure drills before actual projects

Use a disposable repo and an isolated machine. Check duplicate Todo events,
controller restart during workspace creation, CLI prompt timeout after
delivery, missing pane, missing completion ACK, altered plan after approval,
API outage, repeated plan comment, missing state file, and PR creation
failure. The controller must either reconcile the existing work or stop in a
visible recovery phase; never create a second independent dispatch.

The controller currently errs on the safe side: some events require manual
intervention. Lack of duplicate starts is prioritized over liveness.
