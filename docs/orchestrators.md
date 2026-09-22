# Running the dispatchers under other orchestrators

The plugin's seven `dispatch-*` skills are written as a Claude Code plugin, but the orchestration
procedure itself is plain Markdown plus shell commands — herdr does the lane control, and every
signal a sweep needs is on disk. Any agent CLI that (a) can read `SKILL.md` files, (b) can run
shell commands, and (c) runs inside a herdr pane can be the orchestrator. This file records what is
**verified** for each non-Claude orchestrator, and the three Claude-isms you must substitute.

Claims below were verified on 2026-09-15 against herdr 0.9.0, codex-cli 0.154.0 and Kimi Code CLI
0.43.1, on macOS.

## The three Claude-isms to substitute

1. **The supervision timer (§7).** The skills invoke Claude Code's `loop` skill every 5 minutes.
   Substitutes per orchestrator below. The timer only ever fires one thing: a `--resume` sweep, so
   any mechanism that can deliver `/dispatch-<agent> --resume` (or its equivalent prompt) into the
   orchestrator's pane works.
2. **The dispatch confirmation (§3).** Claude Code's `AskUserQuestion` presents the lane plan. Other
   orchestrators should print the plan and **stop**, waiting for a plain-text confirmation —
   behaviourally identical, one less interactive widget.
3. **`allowed-tools` frontmatter.** Claude's permission syntax (`Bash(herdr:*)`, …). Both codex and
   Kimi tolerate and ignore unknown frontmatter keys (verified), so no edit is needed — just run
   each orchestrator in an approval posture where `herdr`, `git`, `gh`, `jq`, `python3` shell calls
   can run unattended, or expect approval prompts.

## Kimi Code CLI as orchestrator — zero code changes (verified)

- **Skill loading:** symlink or copy each `skills/dispatch-*` directory into `~/.kimi-code/skills/`
  (user scope). Verified: a symlinked `dispatch-cursor` appears in Kimi's skill listing with its
  description parsed correctly, `allowed-tools` frontmatter tolerated.
- **Confirmation (§3):** Kimi has `AskUserQuestion`; works as written.
- **Timer (§7):** Kimi has `CronCreate` — a cron task whose prompt is re-injected into the session
  on each fire. Arm `*/5 * * * *` with a prompt naming the run id and telling the session to run
  one `--resume` sweep per the skill files. Same lifecycle caveat as Claude's `loop`: the timer
  dies with the session and `--resume` re-arms it. Verified end-to-end: a Kimi session dispatched a
  cursor lane, supervised it on a `CronCreate` timer, verified and published it (see below).
- **Trust dialog:** Kimi shows its own folder-trust prompt on a fresh worktree
  (`Trust this folder` / `Don't trust`); herdr reports the pane `idle` through it. Resolve once —
  the choice is remembered for that folder.
- **Notify-back:** verified — an external `herdr agent prompt <pane>` into a live Kimi session is
  executed as an instruction.

## codex as orchestrator — works, with packaging and timer caveats (verified)

- **Plugin install:** codex's plugin system accepts this repo's marketplace as-is:

  ```
  codex plugin marketplace add Yansoul/herdr-dispatch --ref dispatch-cursor
  codex plugin add herdr-dispatch@herdr-dispatch
  ```

  The repo carries a `.codex-plugin/plugin.json` (with `"skills": "./skills/"`) for exactly this.
  Verified: after install, a codex session lists `herdr-dispatch:dispatch-codex`,
  `herdr-dispatch:dispatch-cursor`, `herdr-dispatch:dispatch-grok`, `herdr-dispatch:dispatch-opencode`
  (verified when those were the four; `dispatch-devin` and `dispatch-mimo` resolve the same way, from the same
  `skills/` directory).
- **Invocation is model-driven, not slash-driven.** Typing `/dispatch-cursor` into codex returns
  `Unrecognized command` (verified). Instead tell codex to use the skill: "用
  herdr-dispatch:dispatch-cursor 技能派发：…". The skill body then loads normally.
- **Symlink caveat (verified).** codex's *plugin install cache* (`~/.codex/plugins/cache/…`) copies
  the tree and **drops symlinks** — each skill's `references/plan.md` and `references/supervise.md`
  go missing, and every §2–§4 / §6b–§8 cross-reference dangles. The plugin ships a `SessionStart`
  command hook (declared in `.codex-plugin/plugin.json`) that re-materializes both files into every
  `dispatch-*/references/` under the cache at each session start, so installs and upgrades
  self-heal — trust the hook once when codex flags it for review. If your codex build does not run
  plugin hooks, materialize the links by hand:

  ```bash
  cd ~/.codex/plugins/cache/herdr-dispatch/herdr-dispatch/*/skills
  for d in dispatch-*/references; do cp _shared/plan.md _shared/supervise.md "$d/"; done
  ```
- **Timer (§7):** codex has **no in-session scheduler** (verified: `in_app_local_automation` is the
  desktop app's Scheduled surface; the CLI exposes no recurring-prompt mechanism). Use an external
  scheduler poking the pane — both injection channels are verified to be obeyed by a live codex
  session:

  ```cron
  */5 * * * *  herdr agent prompt <orch-pane> "Run one dispatch-<agent> --resume sweep for run <run-id> now."
  # or, codex-native:
  */5 * * * *  codex queue --thread <session-uuid> --message "Run one dispatch-<agent> --resume sweep for run <run-id> now."
  ```

  Unlike the in-session timers, an external cron outlives the orchestrator session — add the
  run id to the state file and make the cron job's first action "exit silently if no such run or
  all lanes terminal", and delete the cron entry when the run ends.
- **Confirmation (§3):** codex stops and asks in plain text; no changes needed beyond reading the
  plan summary as the question it is.
- **Trust dialog:** codex shows its directory-trust modal on a fresh worktree
  (`1. Yes, continue`) and herdr reports the pane ready through it — resolve with
  `herdr agent send-keys <pane> enter` before priming (same pattern the codex executor driver uses).

## What is NOT yet verified

- A full codex-orchestrated dispatch from planning to PR (the `--resume` sweep path under codex is
  verified; a whole run is not).
- grok / opencode as orchestrators — same substitution rules should apply, but nothing was
  exercised.
- Windows. Everything above is macOS.
