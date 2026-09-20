---
name: dispatch-devin
description: Dispatch one or more tasks to devin agents in herdr workspaces — the orchestrator designs each lane's plan and acceptance criteria, devin works through them nudge-driven — supervise them to completion, then push, independently review, and merge each lane's pull request. Use when the user asks to dispatch/fan out/派发 tasks to devin agents or herdr lanes, to run several devin tasks in parallel worktrees, or to resume supervision of an existing dispatch-devin run (`--resume`).
argument-hint: '<task-1>; <task-2>; … [--lanes N] [--base <ref>] [--no-yolo] [--yolo] [--draft] [--no-pr] [--no-automerge] [--resume] [--no-loop]'
allowed-tools: Read, Write, Edit, Glob, Grep, TodoWrite, AskUserQuestion, Skill, Bash(herdr:*), Bash(git:*), Bash(gh:*), Bash(jq:*), Bash(python3:*), Bash(mkdir:*), Bash(ls:*), Bash(test:*), Bash(date:*), Bash(mv:*), Bash(cat:*), Bash(printf:*)
---

# Dispatch tasks to devin agents running under herdr

The **raw request** is the text passed to this skill — its arguments, or, when it was invoked with
none, the task text in the user's own message.

You are an **orchestrator**. You do not implement the tasks yourself. You split the request into
lanes, give each lane its own herdr workspace and its own devin agent, and then keep those agents
alive and moving until every lane genuinely finishes. **You do the planning; devin does the
executing**: each lane gets a plan and acceptance criteria you author and the user confirms (§3).
Devin has **no goal mode** — a lane stops after every turn and the supervision sweep's continuation
prompt is what picks it up again (§6c `idle_incomplete`), so the §7 timer is the engine here, not a
repair path. A lane is not finished when its agent stops — it is finished when its work is verified,
its branch is pushed, and its pull request is open, independently reviewed, and merged (§6f, §6j).

## How to read this skill

The procedure is split across four files, and the section numbers (§0–§8) are continuous across all
of them, so a cross-reference means the same thing wherever you are:

| Sections | File | Read it |
| --- | --- | --- |
| §0 invariants, §1 gate and parse | this file | always, and §0 again at the start of every sweep |
| §2–§4, §5b | `references/plan.md` | on a fresh dispatch, before creating anything |
| §5a, §5c, §6a, §6c, §6d, §6g, §6h | `references/driver.md` | everything devin-specific: launch, probe, classify, steer |
| §6b, §6e, §6f, §6i, §6j, §7, §8 | `references/supervise.md` | before the first supervision sweep |

`references/plan.md` and `references/supervise.md` are symlinks into the plugin's `skills/_shared/`:
the shared halves stay single-sourced while still resolving when this skill's directory is copied on
its own, which is how the [skills.sh](https://skills.sh) installer places it. Both are read by path,
not invoked.

## §0 Invariants — reread every sweep, never work from memory

1. **The state file is the only truth.** `~/.claude/dispatch-devin/<run-id>/state.json`. Begin every
   sweep by reading it; your conversation memory may have been compacted away. Rewrite it atomically
   (write `.tmp`, then `mv`) at the end of every sweep.
2. **Judge a lane from disk, not from the screen.** Devin records every session in
   `~/.local/share/devin/cli/sessions.db` — per-message token counts, turn boundaries and activity
   timestamps. Terminal output is the fallback, never the primary signal. The db is shared by every
   devin session on the machine: always filter by the lane's own session id, and query it read-only.
3. **`agent_status` alone never means "finished", and it can lie outright.** A lane reads `done`
   when unseen work ends — but it reads the same when the prompt was swallowed and when a permission
   selection list is parked on screen (verified). Always corroborate (§6). The same goes for a
   lane's notify-back message (§5b): it is a doorbell that starts a sweep sooner, never evidence
   that skips §6e.
4. **Never touch what you did not create.** Act only on ids recorded in the state file. Never
   `herdr server stop`. Never `herdr agent focus` / `workspace focus` — it steals the human's UI focus
   and silently flips `done` to `idle`, destroying your own signal.
5. **Never destroy work; publish only what you verified.** Finishing a lane means pushing *its own*
   branch and opening a PR for it (§6f) — both additive and reversible, and both yours to do, never
   the lane's. Everything else stays forbidden: never force-push (`--force`, `--force-with-lease`),
   never push the base branch or any branch absent from the state file, never merge outside the
   §6j gate, never `worktree remove`. Print those commands and let the user run them: `worktree remove` kills the
   running devin process and deletes uncommitted changes even without `--force`.
6. **Never improvise a lane's blast radius wider than its brief.** Under the default
   `--permission-mode dangerous` there is no approval overlay to catch a lane that wanders — the
   worktree and the §5b boundaries are the whole fence. In particular: no lane briefed to push,
   merge, or open a PR, and in §6g never pick a permission option that widens the lane's posture
   (devin's list offers `switch to bypass mode` — that one is never yours to pick).

---

## §1 Gate and parse

Run `test "${HERDR_ENV:-}" = 1`, `test -n "${HERDR_PANE_ID:-}"` and `herdr agent list`. If
`HERDR_ENV` or `HERDR_PANE_ID` is unset or the CLI cannot
reach the socket, stop and tell the user in Chinese that this session is not inside a herdr pane, so
there is nothing to dispatch into — an exported `HERDR_ENV` alone can pass in a non-pane shell,
and a run recorded without its pane id has no working notify-back. Do not install or launch herdr,
and do not run devin yourself.

Parse flags from the raw request; everything else is task text.

| Flag | Meaning | Default |
| --- | --- | --- |
| `--lanes N` | cap on concurrent lanes, 1–16 | 16 |
| `--base <ref>` | base ref for lane branches | `origin/<current>` if it exists, else current branch |
| `--no-yolo` | launch devin under the user's own permission config instead of `--permission-mode dangerous` | off — **yolo is the default** |
| `--yolo` | accepted and explicit, but redundant: this is already the default | on |
| `--draft` | open pull requests as drafts instead of ready for review | off — **ready for review is the default** |
| `--no-pr` | push each verified lane but stop there; print the `gh pr create` command instead | off |
| `--no-automerge` | stop at open PRs — no independent review, no merge; the human merges | off — **review-and-merge is the default** |
| `--resume` | skip §2–§5 (this gate and parse still run); run ONE supervision sweep over the existing state file | off |
| `--no-loop` | do not arm the recurring supervision loop after dispatch | off |

There is no `--compact-at`: devin compacts its context automatically in the background (and
publishes no context window on disk), so there is nothing for a sweep to schedule a compaction
against. Compaction count is still probed and reported (§6a).

**Every lane gets its own git worktree. This is not a flag and there is no opt-out.** With approvals
bypassed by default (§5c) and devin's `--sandbox` not enabled, the worktree boundary is the only
thing left keeping one lane's mistakes out of the other lanes and out of the user's own checkout.
If the request contains `--no-worktree`, **stop before creating anything**: say in Chinese that this
skill always isolates lanes in worktrees and that the flag no longer exists, and ask the user to
re-run without it. Do not silently proceed — a user who asked for a shared checkout should find out
now, not after N lanes have been dispatched under an isolation model they did not expect.

With `--resume`, first locate the run — conversation memory may be gone (§0.1): scan
`~/.claude/dispatch-devin/*/state.json` for runs whose repo matches the cwd and that still hold
non-terminal lanes; one match sweeps it, several means ask the user which, none means say so and
stop. Then read `references/driver.md` and `references/supervise.md` and go to §6. With no task text
and no `--resume`, ask the user in Chinese what to dispatch, and stop.

Otherwise — a fresh dispatch — read `references/plan.md` now and continue at §2.
