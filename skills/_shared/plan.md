# Dispatch — §2 to §5b (agent-independent)

Shared by every `dispatch-*` skill in this plugin. Nothing here depends on which coding agent runs
the lanes: it covers the run's bookkeeping (§2), the lane plan the orchestrator records (§3), the lane
worktrees and terminals (§4), and the brief written into each lane's checkout (§5b).

Runtime preflight (§5a) and launch (§5c) live in `references/driver.md`. Shared invariants and
parsing (§0–§1) live in `references/entry.md`, model selection in `references/routing.md`, and
verification/publication (§6–§8) in `references/supervise.md`. Section numbers are shared.

Throughout, **the agent** means omp, and **the driver** is the shared `references/driver.md`.
The selected preset chooses a model; magpie owns supplier routing. Every lane runs omp.

---

## §2 Repo, run id, state file

Resolve `git rev-parse --show-toplevel`. Empty means "not a repo" — there is nothing to branch a
worktree from, so stop and tell the user in Chinese that dispatch needs a git repo. Do not fall back
to sharing the cwd. If `git rev-parse --git-dir` and `--git-common-dir` differ you are in a linked
worktree; stop and ask the user to re-run from the main checkout.

Fetch `origin` when it exists and prefer `origin/<branch>` as the base. With no remote, use
the local branch and report that publication is unavailable.

Run id: six lowercase alphanumerics derived from `date +%s`. State dir
`~/.claude/<skill-name>/<run-id>/` — `<skill-name>` is this skill's own name, so two dispatchers
running different agents over the same repo never share a state tree. `mkdir -p` it. If another run
dir for this repo still holds non-terminal lanes, do not silently start a second one — ask the user
whether to resume, archive, or abort.

Record `schema_version: 2`, `skill`, `agent_kind: "omp"`, `flags`, `repo`, `base`, the selected
magpie `model`, `thinking`, and per-lane routing fields specified in `references/driver.md`.
Record `orchestrator_pane` from `$HERDR_PANE_ID` on `herdr` or `$HC_TERMINAL_ID` on `hc` (§1 decides
which; the field name is historical and holds either terminal id). Lanes notify completion by
prompting this terminal (§5b), and each brief needs the id verbatim — never leave a lane
to find its orchestrator with `herdr agent list` / `hc ls`. On `herdr` the id stays valid until the
pane closes or is moved to another workspace (a move re-qualifies it); on `hc` it stays valid while
the terminal lives, and lanes launched with `--outlive-parent` keep running after this session's
process ends. Either way the id never proves *who* is inside: if this
session ends, the §7 timer dies with it, later rings error out — or land as unsolicited text in
whatever session occupies the terminal by then — and the run comes back only when a human re-runs this
skill with `--resume`; that resumed sweep re-arms the loop and re-records `orchestrator_pane` (§7),
restoring supervision, though briefs already written keep ringing the old terminal — the timer covers
what those rings miss. Within a live session, the §7 timer is the backstop for every ring that
misses.

**Publishing preflight.** A lane finishes with *you* pushing its branch and opening its PR (§6f),
so settle *now* — before a single lane worktree exists — whether that will be possible, and record
each answer in the state file:

- does `origin` exist (`git -C <repo> remote get-url origin`);
- does `gh auth status` succeed, and does `gh repo view --json nameWithOwner -q .nameWithOwner`
  resolve the target repo;
- is the **PR base** — the `--base` ref with any `origin/` prefix stripped — an actual branch on
  origin (`git -C <repo> ls-remote --exit-code --heads origin <pr-base>`).

Do not install `gh`, do not authenticate it, and do not create the missing branch. None of these
failing is a reason to abort: they only narrow what §6f can do, and §3 must tell the user up front
which half they will be finishing by hand.

**Agent preflight.** Ask the driver's §5a what it needs verified once per run rather than per lane —
typically that the agent's executable resolves and which version it is. Record the version string:
every "(verified)" claim in a driver was verified against a specific version, and a mismatch is
worth one report line in §8, not an abort.

---

## §3 Plan the lanes

Split the task text on numbered items, newlines, or `;` — whichever the user actually used.

Then **group** them for high cohesion within each lane and low coupling between lanes. Result
quality takes priority over concurrency; maximize independent work within that constraint:

- Each lane owns a coherent outcome, the implementation needed for it, and local self-checks.
  Keep tasks together when they edit the same files, depend on each other's unfinished output,
  or must change together to preserve a shared behavioral invariant.
- Actively look for independent outcomes within a large task. Split them into different lanes only
  when each can finish using the existing code and established interfaces, without editing the same
  files or coordinating intermediate work with another lane. Different files alone do not prove
  independence; belonging to the same module alone does not require a single lane.
- Do not introduce new dependencies, cross-lane handoffs, or shared implementation scaffolding
  merely to increase terminal count. If independence is uncertain, investigate before splitting or keep
  the work in one lane. Inside a lane, tasks remain an ordered checklist.
- The top-level dispatch session defines acceptance criteria and owns final acceptance (§6e).
  Lanes implement and self-check; they do not accept their own or another lane's results.
- Never exceed `--lanes N` (default and hard max 16). If grouping yields more, merge the most related
  ones and say which and why. Do not pad the other way: three independent tasks make three lanes.
- When lanes > 4, report that lanes sharing a magpie upstream/account also share its quota.
  Routing groups may span accounts; do not claim that every model shares one account.

Per lane derive:

- `slug` — a 2–3 word kebab-case summary of the lane's work (e.g. `add-owner-filter`,
  `fix-ws-timeout`): lowercase letters, digits and `-` only, starting with a letter (reword a
  digit-leading summary). Describe the work, not the mechanics — the slug is the readable part of
  everything the user sees: lane name, workspace label, worktree, branch. Slugs are unique within
  the run: two similar tasks get distinguishing words (`fix-login-web`, `fix-login-mobile`), never
  the same slug twice — the branch below drops `<n>`, so two lanes sharing a type and issue would
  produce the same branch name.
- `name` — `<slug>-<n>` with `<n>` the lane number, e.g. `add-owner-filter-1`. Keep it letter-leading
  and ≤32 chars: herdr requires `[a-z][a-z0-9_-]{0,31}`, hc accepts `1-32 of a-z 0-9 - _`, and the
  herdr form satisfies both. Shorten an overlong slug by dropping whole words from the end — still
  letter-leading, no trailing hyphen — until the name fits 32 chars. Names carry no run id and are
  released only when an agent exits, so check `herdr agent list` and `herdr workspace list`, or
  `hc ls` on `hc`, before
  dispatch; on a collision, shorten further and append the run id's *last* three characters
  (`<slug>-<n>-<xyz>`, still within 32 — the tail of a timestamp-derived id is its fast-moving end,
  the head barely changes between same-day runs), and re-check until the name is actually free.
- `type` — the branch-type prefix that best fits the lane's overall work, with the usual
  Conventional-Commits meanings: `feature` (or `feat` — interchangeable in the branch, but in
  commit messages and PR titles the Conventional-Commits token is always `feat`) for a user-facing
  feature, `fix` for a user-facing bug fix, `docs`, `style`, `refactor`, `test`, or `chore`. One
  type per lane; a mixed lane takes the type of its primary objective.
- `issue` — the GitHub issue number the lane addresses, read from the task text (`#123`, a full
  issue URL, or wording like "issue 123"). Never invent one: a lane whose tasks name no issue has
  none; a missing optional issue number does not block dispatch.
- `branch` — `<type>/<issue>-<slug>`, the slug serving as the alias (the issue's keyword) — e.g.
  `feature/1-init`, `fix/42-ws-timeout`. When the lane has no issue number, drop that segment:
  `<type>/<slug>`.
  Nothing in this name embeds the run id, so it can collide with a branch that already exists —
  locally, on origin, or checked out in another worktree. Check
  `git -C <repo> branch --list <branch>`, `git -C <repo> ls-remote --heads origin <branch>` and
  `git -C <repo> worktree list` before dispatch; on a collision, append the run id's last three
  characters (`<type>/<issue>-<slug>-<xyz>`).
- `tasks` — the ordered checklist.
- `plan` — the lane's implementation plan, authored by **you**. The lane's agent does not plan for
  itself in this skill — it executes the plan you hand it — so this must be executable as written:
  ordered steps naming the files or modules each one touches, key decisions with a one-line
  rationale each, and where a route is genuinely open, the fork named with the default you chose, so
  the user can see the direction before execution. Ground every step in the repo — a
  quick Glob/Grep/Read of the code it names, never guesswork. Steps, not prose: the lane executes
  this top to bottom and records any forced deviation in `.dispatch/progress.md` (§5b).
- `acceptance` — the lane's acceptance criteria (presented to the user as 验收标准), authored by
  **you**: the explicit, checkable criteria that define done. Build them from the repo's real check
  commands — found in `package.json` / `Makefile` / `justfile` / CI config, never invented — each
  with its expected outcome, plus behavioural criteria stated concretely enough to verify from the
  diff or a command. A repo with no automated checks gets criteria over tree state and diff content
  instead, plus an explicit "no automated checks in this repo". These criteria are what the lane
  works toward and self-checks before writing DONE (§5b). The top-level dispatch session re-runs
  them for final acceptance (§6e); DONE is a completion claim, not acceptance. Write nothing here
  you cannot check yourself.

Present the plan in Chinese: the lane table (lane / 分支 / 包含的任务), and under each lane its
实施计划 (the ordered steps) and 验收标准 bullets. Below that, state in **three** lines, so the user
sees all of them before anything is created:

- **which agent and which approval posture** the lanes will run in — the driver's §5c supplies the
  exact wording, including what `--no-yolo` does and does not change for this agent. Never describe
  a safety boundary this agent does not actually have.
- **how each lane is driven** — the driver's §5c supplies this too: an autonomous objective the
  agent continues on its own, or a single prompt that the supervision sweep re-nudges (§6c
  `idle_incomplete`). Say which, because it changes how long a silent lane may legitimately stay
  silent.
- **what happens when a lane finishes** — by default
  `验证通过后自动 push 到 origin，对 <pr-base> 开 PR（ready for review，会触发 CI 和 reviewer 通知），
  再由独立 reviewer subagent 审查、按需修复并自动合并`,
  or the degraded form the §2 preflight actually found (`--draft` 开草稿 PR，草稿不自动合并 /
  `--no-automerge` 开到 PR 为止，review 和合并留给用户 / `--no-pr` 只 push，PR 命令会打印出来 /
  `gh 未登录，只 push，PR 命令会打印出来` / `PR base 不在 origin 上，只 push，PR 命令留待你补 base` /
  `无 origin，只能本地提交`). Never promise a PR the preflight says you cannot open.

Present this concrete plan as an informational update, then proceed directly to §4. The dispatch
request authorizes routine lane grouping and creation of the task's worktrees and terminals;
never ask the user to confirm the lane table, terminal allocation, or permission to start them. Choose
routine implementation details from repository conventions. Ask once with the host's question tool
(or plain text) only when unresolved scope or a material choice requires the user's decision; do not
turn that question into a blanket confirmation of the allocation. Record the plan and acceptance
criteria verbatim without waiting for an acknowledgement. If the user changes the plan, incorporate
the change before dispatch. An explicit request to review the plan before execution still applies.

---

## §4 One worktree (and terminal) per lane

**On `herdr`, `herdr worktree create --cwd <repo>` creates TWO workspaces**, not one: the linked
worktree *and* a workspace for the base repo itself. So snapshot ids before and after and record
every new one, or cleanup will leak:

    herdr workspace list | jq -r '.result.workspaces[].workspace_id'   # before
    herdr worktree create --cwd <repo> --branch <branch> --base <base> --label <lane> --no-focus
    herdr workspace list | jq -r '.result.workspaces[].workspace_id'   # after — diff for new ids

`herdr workspace create --cwd <cwd>` is **not** an alternative here — it would point a lane at an
existing checkout, which §1 forbids. `worktree create` is the only way a lane is born. Nor is the
agent's *own* worktree feature (some of these CLIs have one): a lane must live in the worktree this
run created and recorded, because that path is what §6e verifies and §6f pushes. The driver says so
explicitly where its agent offers one.

Read ids from the JSON, never guess — workspace ids are opaque handles like `w4B`, not `w1`:
`.result.workspace.workspace_id`, `.result.root_pane.pane_id`, `.result.worktree.path` (the lane's
checkout).

**On `hc` there is no workspace entity.** A lane is a recorded git worktree plus one hc terminal
created at §5c — no shell pane exists beforehand, and preflight runs through `hc exec` (driver §5a):

    git -C <repo> worktree list --porcelain                        # before
    git -C <repo> worktree add <checkout> -b <branch> <base>
    git -C <repo> worktree list --porcelain                        # after — record the new path

Record the checkout path and the lane `name`; the terminal id and its `dispatch.*` labels are
recorded when §5c creates it. `hc` needs no id snapshotting beyond that — there are no workspace
ids to leak, and cleanup is the recorded terminal plus the recorded worktree path (§8.1).

If a create fails because the name, label or worktree path is already taken — a §3 collision
surfacing at claim time, or a stale checkout directory neither list could show — rename per §3's
collision rule and retry once. On any other failure, record the lane as `failed` with the error,
continue with the rest, and report it at the end — one broken lane must not abort the dispatch.
Append each lane to the state file as it is created so a crash mid-fan-out is recoverable.

---

## §5b Write the brief into the lane's own checkout

(§5a pre-flights the terminal and §5c launches the agent — both in the driver. Write the brief between
them: the file must exist before the agent is primed.)

`<checkout>/.dispatch/TASK.md`, kept out of git:

    mkdir -p <checkout>/.dispatch
    git -C <checkout> rev-parse --git-path info/exclude

Append `.dispatch/` once to the resolved exclude file. In a linked worktree `.git` is a file,
not a directory; never write `<checkout>/.git/info/exclude` directly.

Every lane has its own checkout, so `.dispatch/` never collides between lanes and needs no per-lane
subdirectory.

The brief contains, in English: **objective**; the **plan** — the §3 plan exactly as recorded,
with a standing instruction: execute it in order, and when reality contradicts a
step, record the deviation and its reason prominently in `.dispatch/progress.md` instead of
silently re-designing; the **checklist** as `- [ ]` items; the **acceptance criteria** — the §3
criteria exactly as recorded, with the framing that they, not the checklist ticks, define done:
DONE is written only when every criterion verifiably holds; **boundaries** (work only in this
checkout, never `cd` to the main checkout, never touch another lane's files, never push, never
merge, never open a pull request — committing is where your job ends, and the orchestrator verifies,
publishes, independently reviews and merges the branch); and the **commit policy** below, quoted
into the brief in full.

> **Commit policy.** Commit continuously as you work, never as one lump at the end. Each commit is one
> coherent unit — a module, a file, a self-contained behaviour change — and each message follows
> Conventional Commits: `<type>(<scope>): <description>`.
>
> Pick the granularity by asking what a reviewer would want to read on its own and what a future
> `git revert` would need to take out in one piece. Concretely: a checklist item is at least one
> commit, and a large one is several; a refactor and the behaviour change that follows it are separate
> commits; a new module lands separately from the code that starts calling it; unrelated fixes you
> notice along the way never ride along inside another commit. Stage only the paths belonging to the
> unit you are committing — `git add <paths>`, never `git add -A`. Do not amend or rebase a commit you
> already made; correct it with a follow-up commit instead, because the orchestrator may already have
> read the history.
>
> **Commit coordination.** Follow repository-local commit coordination rules when present. Do not
> invent a machine-specific lock protocol or assume `~/CLAUDE.md` exists. Commit only this lane's
> changes; never remove another process's lock.

Then the load-bearing part:

> **Progress protocol.** Keep `.dispatch/progress.md` current: after each checklist item, rewrite it
> with the checklist and its tick state, what you just did, what you are about to do, and any decision
> a fresh reader would need. Assume your context may be compacted at any moment and this file is all
> you keep. When every checklist item is done, every acceptance criterion holds and `git status` is
> clean, write `.dispatch/DONE` with a one-line summary.

`.dispatch/progress.md` carries more weight the less autonomous the agent is: for a lane driven by
re-nudges (§6c `idle_incomplete`) it is the only thing that tells the next nudge where to resume, so
the driver may strengthen this paragraph — never weaken it.

Then the lane's local resources, with `<run-id>` and `<lane>` substituted the same way as in the
notify-back. A lane runs in yolo mode and routinely starts dev servers, workers and containers; the
orchestrator can only clean up what it can find, so the brief makes them findable and makes the lane
stop them:

> **Local resources.** Everything you start, you stop before you write `.dispatch/DONE`. Start dev
> servers, watchers and databases from this checkout only, and never leave one running in the
> background once the command that needed it is finished (no bare `nohup`, `disown` or trailing `&`
> without a matching stop). Every container you create carries
> `--label dispatch.run=<run-id> --label dispatch.lane=<lane>` and is named
> `dispatch-<run-id>-<lane>-<purpose>`; a compose project is named `dispatch-<run-id>-<lane>`.
> For each long-lived thing, append one line to `.dispatch/resources.md` when you start it
> (`pid=…`, `port=…`, `container=…`, or a temporary directory outside the checkout such as a
> release copy under `/tmp`), and delete that line when you stop it. Do not touch containers, ports or
> processes you did not start, and never stop Docker Desktop or any system-wide database. If
> something cannot be stopped, say so in `progress.md` instead of leaving it silently.

Then the notify-back, so a finished lane rings the orchestrator instead of sitting undiscovered
until the next §7 tick. Write it into the brief with `<orch-terminal>` (the §2 `orchestrator_pane`),
`<run-id>`, `<lane>` and `<skill>` already substituted, using the line for this run's `mux` — the
lane runs it verbatim:

> **Completion notify-back.** Immediately after writing `.dispatch/DONE`, run this exact command
> once:
>
>     herdr: herdr agent prompt <orch-terminal> "[<skill> <run-id>] lane <lane> wrote DONE — run one <skill> --resume --run <run-id> sweep now."
>     hc:    hc send <orch-terminal> "[<skill> <run-id>] lane <lane> wrote DONE — run one <skill> --resume --run <run-id> sweep now."
>
> If it errors or is rejected (e.g. `agent_blocked`), do not retry and do not investigate — the
> orchestrator also polls on a timer and will find `.dispatch/DONE` regardless. This is the only
> multiplexer command in your job: it targets only the terminal named here, and you never read,
> prompt, or send keys to any other terminal or agent.

On `hc` a lane terminal's own status transitions also reach the orchestrator automatically — hc
types a note into the parent terminal when a child finishes, blocks, errors or exits. The explicit
send above still runs: its text carries the resume instruction, which a bare status note does not.

(The herdr skill warns against asking for file output in an initial prompt. That guidance is about
*retrieving long answers*; here the files are a state protocol that must survive compaction.)

---

Now launch the lanes: the driver's §5c. Start every lane before supervising any of them, then read
`references/supervise.md` and continue at §6.
