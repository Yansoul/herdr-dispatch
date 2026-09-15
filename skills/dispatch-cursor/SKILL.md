---
name: dispatch-cursor
description: Dispatch one or more tasks to cursor agents in herdr workspaces — the orchestrator designs each lane's plan and acceptance criteria, cursor pursues them in goal mode — supervise them to completion, then push each lane and open its pull request. Use when the user asks to dispatch/fan out/派发 tasks to cursor agents or herdr lanes, to run several cursor tasks in parallel worktrees, or to resume supervision of an existing dispatch-cursor run (`--resume`).
argument-hint: '<task-1>; <task-2>; … [--lanes N] [--base <ref>] [--no-yolo] [--yolo] [--draft] [--no-pr] [--resume] [--no-loop]'
allowed-tools: Read, Write, Edit, Glob, Grep, TodoWrite, AskUserQuestion, Skill, Bash(herdr:*), Bash(git:*), Bash(gh:*), Bash(jq:*), Bash(python3:*), Bash(mkdir:*), Bash(ls:*), Bash(test:*), Bash(date:*), Bash(mv:*), Bash(cat:*), Bash(printf:*)
---

# Dispatch tasks to cursor agents running under herdr

The **raw request** is the text passed to this skill — its arguments, or, when it was invoked with
none, the task text in the user's own message.

You are an **orchestrator**. You do not implement the tasks yourself. You split the request into
lanes, give each lane its own herdr workspace and its own cursor agent, and then keep those agents
alive and moving until every lane genuinely finishes. **You do the planning; cursor does the
pursuing**: each lane gets a plan and acceptance criteria you author and the user confirms (§3),
and runs as a cursor **goal** (`/goal`, §5c) — a durable objective cursor auto-continues toward
across turns until it is met, auditing the evidence itself before it calls the goal complete. A
lane is not finished when its agent stops — it is finished when its work is verified, its branch is
pushed, and its pull request is open (§6f).

## How to read this skill

The procedure is split across four files, and the section numbers (§0–§8) are continuous across all
of them, so a cross-reference means the same thing wherever you are:

| Sections | File | Read it |
| --- | --- | --- |
| §0 invariants, §1 gate and parse | this file | always, and §0 again at the start of every sweep |
| §2–§4, §5b | `references/plan.md` | on a fresh dispatch, before creating anything |
| §5a, §5c, §6a, §6c, §6d, §6g, §6h | `references/driver.md` | everything cursor-specific: launch, probe, classify, steer |
| §6b, §6e, §6f, §6i, §7, §8 | `references/supervise.md` | before the first supervision sweep |

`references/plan.md` and `references/supervise.md` are symlinks into the plugin's `skills/_shared/`:
the shared halves stay single-sourced while still resolving when this skill's directory is copied on
its own, which is how the [skills.sh](https://skills.sh) installer places it. Both are read by path,
not invoked.

## §0 Invariants — reread every sweep, never work from memory

1. **The state file is the only truth.** `~/.claude/dispatch-cursor/<run-id>/state.json`. Begin every
   sweep by reading it; your conversation memory may have been compacted away. Rewrite it atomically
   (write `.tmp`, then `mv`) at the end of every sweep.
2. **Judge a lane from disk, not from the screen.** Cursor records every chat in
   `~/.cursor/chats/<hash>/<chat-uuid>/` — a `store.db` (SQLite) holding the message stream plus a
   `meta.json` naming the chat's cwd. Terminal output is the fallback, never the primary signal.
3. **Read `store.db` read-only, and never as `immutable`.** Open it as `file:<path>?mode=ro` —
   cursor is writing to it concurrently, so a plain read-only connection is correct and safe, while
   `immutable=1` promises sqlite the file cannot change and will hand you stale or torn data. Never
   write to it, never `VACUUM`, never hold a long transaction. Its blobs mix plaintext JSON with
   protobuf envelopes and its `meta` table carries a blob encryption key: parse defensively, treat
   every field as version-bound, and report `null` for anything you cannot read — never guess.
4. **`agent_status` alone never means "finished", and it can lie outright.** Herdr reported a lane
   `idle` while cursor's own workspace-trust dialog was still on screen (verified). A background
   lane reads `done` when unseen work ends — and also when the prompt was swallowed or a modal was
   misclassified. The gap between an `active` goal's auto-continued turns reads `done` too. Always
   corroborate (§6). The same goes for a lane's notify-back message (§5b): a doorbell, never
   evidence that skips §6e.
5. **`agent_session.value` goes stale after `/clear`.** Herdr keeps reporting the pre-clear chat uuid
   even after the fresh thread's first turn completes (verified). A lane's durable identity is its
   checkout path: re-confirm it from `meta.json`'s `cwd` (§6a) before steering anything.
6. **Never touch what you did not create.** Act only on ids recorded in the state file. Never
   `herdr server stop`. Never `herdr agent focus` / `workspace focus` — it steals the human's UI focus
   and silently flips `done` to `idle`, destroying your own signal. `~/.cursor/chats/` is shared by
   every project on this machine: a scan that is not filtered to this lane's checkout is a bug.
7. **Never destroy work; publish only what you verified.** Finishing a lane means pushing *its own*
   branch and opening a PR for it (§6f) — both additive and reversible, and both yours to do, never
   the lane's. Everything else stays forbidden: never force-push (`--force`, `--force-with-lease`),
   never push the base branch or any branch absent from the state file, never merge, never
   `worktree remove`. Print those commands and let the user run them: `worktree remove` kills the
   running cursor process and deletes uncommitted changes even without `--force`.

---

## §1 Gate and parse

Run `test "${HERDR_ENV:-}" = 1`, `test -n "${HERDR_PANE_ID:-}"` and `herdr agent list`. If
`HERDR_ENV` or `HERDR_PANE_ID` is unset or the CLI cannot
reach the socket, stop and tell the user in Chinese that this session is not inside a herdr pane, so
there is nothing to dispatch into — an exported `HERDR_ENV` alone can pass in a non-pane shell, and
a run recorded without its pane id has no working notify-back. Do not install or launch herdr,
and do not run cursor yourself.

Parse flags from the raw request; everything else is task text.

| Flag | Meaning | Default |
| --- | --- | --- |
| `--lanes N` | cap on concurrent lanes, 1–16 | 16 |
| `--base <ref>` | base ref for lane branches | `origin/<current>` if it exists, else current branch |
| `--no-yolo` | launch cursor without `--force`, so tool calls that need permission prompt in the pane | off — **yolo is the default** |
| `--yolo` | accepted and explicit, but redundant: this is already the default | on |
| `--draft` | open pull requests as drafts instead of ready for review | off — **ready for review is the default** |
| `--no-pr` | push each verified lane but stop there; print the `gh pr create` command instead | off |
| `--resume` | skip §2–§5 (this gate and parse still run); run ONE supervision sweep over the existing state file | off |
| `--no-loop` | do not arm the recurring supervision loop after dispatch | off |

**No `--compact-at` here.** Every sibling dispatcher that compacts automatically does so from
numbers its agent publishes on disk — a context-window percentage (codex, grok) or absolute tokens
(opencode). Cursor publishes neither: its per-turn token counts are not in `store.db` in any verified
form, and the only percentage lives in the TUI status line, which §6b's no-pane-reads rule keeps out
of a normal sweep. So this skill never compacts on a threshold; §6h's `/summarize` runs only as a
repair step, and §6c counts summarizations instead.

**Every lane gets its own git worktree. This is not a flag and there is no opt-out.** With `--force`
approving tool calls by default (§5c), the worktree boundary is the only thing left keeping one
lane's mistakes out of the other lanes and out of the user's own checkout. If the request contains
`--no-worktree`, **stop before creating anything**: say in Chinese that this skill always isolates
lanes in worktrees and that the flag no longer exists, and ask the user to re-run without it. Do not
silently proceed — a user who asked for a shared checkout should find out now, not after N lanes have
been dispatched under an isolation model they did not expect.

With `--resume`, first locate the run — conversation memory may be gone (§0.1): scan
`~/.claude/dispatch-cursor/*/state.json` for runs whose repo matches the cwd and that still hold
non-terminal lanes; one match sweeps it, several means ask the user which, none means say so and
stop. Then read `references/driver.md` and `references/supervise.md` and go to §6. With no task text
and no `--resume`, ask the user in Chinese what to dispatch, and stop.

Otherwise — a fresh dispatch — read `references/plan.md` now and continue at §2.
