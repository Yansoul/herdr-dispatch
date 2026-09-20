# Supervision — §6b, §6e–§6f, §6i, §7, §8 (agent-independent)

Shared by every `dispatch-*` skill in this plugin. The sweep alternates between this file and the
calling skill's `references/driver.md`:

| § | Where | What |
| --- | --- | --- |
| §6a | driver | probe one lane's state from disk |
| §6b | here | poll the fleet, prove each lane is still yours |
| §6c | driver | classify each lane (the table, and its row order) |
| §6d | driver | steer a lane that is parked, blocked, or drifting |
| §6e | here | verify a lane that claims to be finished |
| §6f | here | publish a verified lane — push, open the PR |
| §6g | driver | handle a `blocked` lane / approval overlay |
| §6h | driver | compact or restart a lane |
| §6i | here | close the sweep |
| §6j | here | review, fix, and merge a published lane |
| §7, §8 | here | arm the loop, report |

Reread §0 (in `SKILL.md`) before every sweep.

## The probe contract

§6c's table and everything below are written against the fields the driver's §6a promises. A driver
must report, per lane, at least:

| Field | Meaning | Missing when |
| --- | --- | --- |
| `session` | the agent's own id for this lane's live thread, as recorded in the state file | the agent exposes none — then the driver says what it uses for identity instead |
| `turn_state` | `working` (a turn is in flight) / `complete` (the last turn ended) / `unknown` | the agent's on-disk record cannot distinguish them |
| `used_pct` | percent of the context window in use, or `null` when the agent publishes no context window | — |
| `compactions` | how many times this thread has been compacted | — |
| `mtime` | last write to the lane's own on-disk record, for stall detection | — |
| `probe` | `ok` / `unavailable` with a reason | — |

Optional fields a driver may add — `goal_status`, `out_of_room`, `commits`, `todo` — are used only
by rows its own §6c table defines. **A field a driver does not report is never assumed**: a sweep
that cannot see `used_pct` does not guess one, it reports `null` and leans on `mtime` and
`turn_state` instead.

---

## §6b Poll the whole fleet in one call

`herdr agent list` returns every lane's `agent_status` and `state_change_seq` at once. Do not read
panes during a normal sweep — it costs context and tells you less than the lane's own on-disk record
does.

Names alone do not prove identity. Lane names carry no run id and are re-usable the moment an agent
exits, so a name in your state file can now belong to a later run's agent or to one the user started
by hand. Before steering any lane by name — prompt, send-keys, compact — confirm the session id
from `herdr agent get <lane>` (or the driver's own identity check, when its agent has no herdr-visible
session) still matches the one recorded in the state file (§6a). On a mismatch, stop steering and
diagnose — the three cases look alike and only one is yours to act on:

- the name resolves to an agent in some *other* workspace → a stranger re-claimed a released name.
  Never touch it (§0.4); surface the lane.
- the name resolves in the lane's own recorded pane, under a different id → not necessarily a
  stranger: the id also changes when a fresh thread starts in the same agent process (the driver's
  §6h restart recipe — or the user's own hand). If the state file shows a restart in flight, finish
  that recipe; otherwise surface it to the user instead of guessing, because steering someone else's
  thread and abandoning your own look identical from here.
- the name resolves to nothing → the agent exited. A non-terminal lane is relaunched per the
  driver's §5c on its recorded pane once it is back at a shell (§5a's checks apply again), then
  re-primed. The §6h restart recipe does not apply — it prompts a live agent, and there is none
  left here.

**Prompt guard — the one sanctioned exception to the no-pane-reads rule.** Immediately before *any*
input this sweep sends a lane — a slash command, a steering or continuation prompt — do ONE
`herdr agent read <lane> --source visible`. If a selection list or modal is parked there, send
nothing: a prompt submitted at a parked list presses its highlighted default. Resolve it first
(§6d/§6g).

---

## §6e Verify a finished lane

`agent_status` is not evidence, and neither is the lane's own `.dispatch/DONE`:

    git -C <checkout> status --porcelain              # must be empty
    git -C <checkout> log --oneline <base>..<branch>  # must be non-empty

plus the **acceptance criteria, re-run by you**: execute each §3-confirmed criterion's command from
TASK.md in the lane's checkout and require its expected outcome; judge the non-mechanical criteria
from the diff and `.dispatch/progress.md`. The lane already claims they pass — that claim is what
you are checking, not what you are accepting. Any agent-side "objective complete" signal the driver
reports is corroboration that the agent considers itself done, never a substitute for the criteria.
Also read `progress.md` to confirm every checklist item is ticked and to see whether the lane
recorded a deviation from the §3-confirmed plan. A recorded deviation is not a failure — judge the
result on its merits — but it must surface in the PR body (§6f) and the §8 report, never silently.
If a lane claims done but fails any of these, send a corrective prompt and keep it open. Never
report a half-finished lane as complete.

**Commit granularity is a report line, not a gate.** Compare the commit count against the checklist
length; a multi-item lane that produced a single commit ignored §5b's policy. Record it and surface it
in §8, but do **not** hold the lane back and never ask the agent to rewrite history to fix it —
amending or rebasing an already-verified branch risks the work itself, which costs far more than an
ugly history. Coarse commits are a note on the PR, not a reason to redo it.

Only a lane that passes **every** one of these becomes phase `verified`, and only a `verified` lane is
eligible for §6f. Nothing unverified is ever pushed — that is the whole reason this step runs first.

---

## §6f Publish a verified lane — push the branch, open the pull request

**You publish; the lane never does.** The agents are briefed "never push, never merge, never open a
PR" (§5b) precisely so that the one operation which leaves the worktree and reaches a shared remote
stays behind §6e's verification, in the hands of the one participant that has actually checked the
work. A lane that asks to push is still an anomaly, not a shortcut — surface it per §6g, never
approve it.

Publishing is **idempotent**. It runs on every sweep until it succeeds, so record `pushed_sha`,
`pr_number`, `pr_url` and `publish_attempts` in the state file and skip whatever is already done.

**1. Preconditions — degrade with a recorded reason, never with a guess.** Re-read the §2 preflight:

- no `origin` → nothing to push to; leave the lane `verified`, report it as local-only;
- `gh` missing or unauthenticated, or `--no-pr` → do step 2, then stop and print the exact
  `gh pr create` command for the user;
- the PR base is not a branch on origin → do step 2, but do **not** open a PR against a substituted
  base. A PR aimed at a branch the lane did not fork from shows a diff that is not the lane's work.
  Report it and print the command with the base left for the user to fill in.

**2. Push exactly one branch, by explicit refspec:**

    git -C <checkout> push -u origin refs/heads/<branch>:refs/heads/<branch>

The refspec is spelled out on purpose: never `--all`, never `--force` or `--force-with-lease`, never
the base branch, never a branch that is not in the state file. A rejected non-fast-forward push means
something else moved that branch — stop, record it, surface it; force-pushing here would destroy
whatever moved it. No `--no-verify`: pre-push hooks are part of the repo's checks.

**3. Reuse an existing PR before creating one:**

    gh pr list --repo <owner/repo> --head <branch> --state all --json number,url,state

Non-empty → record it and stop; the push in step 2 already updated it. `gh pr create` errors out on a
head branch that already has a PR, and a sweep that treats that error as failure will retry forever.

**4. Write the body to a file, then create:**

    gh pr create --repo <owner/repo> --base <pr-base> --head <branch> \
      --title '<conventional-commit title>' \
      --body-file ~/.claude/<skill-name>/<run-id>/<lane>-pr.md

- **Every argument is explicit, and that is load-bearing.** `gh pr create` prompts interactively for
  anything it cannot infer — and on a fork it asks which repo to target even when it can. An
  interactive prompt inside a non-interactive Bash call hangs until the timeout, so `--repo` (from
  `gh repo view --json nameWithOwner -q .nameWithOwner`), `--base`, `--head`, `--title` and
  `--body-file` are all mandatory here. Use `--body-file`, not `--body`: a multi-line body through the
  shell is where quoting breaks.
- **Ready for review is the default**, so no `--draft` flag: §6e has already established that the
  tree is clean, the commits are real and the repo's own checks pass, and a PR nobody can review
  without first clicking a button is a PR that sits. Opening ready does page reviewers and CODEOWNERS
  and does start CI, which is the point — but it also means the provenance line in the body is the
  only thing telling them an agent wrote this, so never drop it. Pass `--draft` to land the run
  quietly instead.
- **Title:** Conventional-Commits shaped, derived from the lane's objective — the commit subject when
  the lane produced exactly one commit, otherwise `<type>(<scope>): <objective>`, with the type
  agreeing with the branch's type prefix (a `feature` branch normalizes to `feat`). No run ids, lane
  names or raw branch strings in the title; those belong in the body.
- **Body, in English:** the checklist with its final tick state; a `Closes #<issue>` line when the
  lane carries an issue number, so the merge closes it; a short summary distilled from
  `.dispatch/progress.md` (that file is git-excluded per §5b, so the reviewer cannot open it — carry
  it over, do not link to it); the acceptance criteria with each one's verified outcome (§6e);
  any recorded deviation from the §3-confirmed plan, stated as such; and a provenance line naming
  the run id, the lane, **which agent and version wrote the code**, and the approval posture it ran
  under. The reviewer should know what they are reading before they start reading it.

**5. Close the lane.** Record `pr_url` and set the phase to `published`. On failure, record the
stderr and bump `publish_attempts`; after 3 failed attempts stop retrying, record that as the
lane's degrade reason, leave it `verified`, and surface it with the exact command for the user to
run by hand. The recorded reason — from here or from step 1 — is what makes a `verified` lane
terminal for §7 and keeps §6c's `unpublished` row from re-matching it forever. A publish loop that
retries forever is worse than one that hands the command back.

---

## §6j Review and merge a published lane

`published` ends a lane only when the run opted out — `--no-automerge`, `--draft`, or `--no-pr`.
Otherwise the contract carries the PR across the line itself: an independent review, fixes for what
it finds, and the merge. It runs per lane, only ever on PRs this run opened, and it is idempotent
like §6f — record `review_rounds`, findings, and `merge_sha` in the state file and skip whatever a
prior sweep already did.

**1. Review with eyes that did not write the code.** Spawn a subagent — a fresh, independent agent
with no share in this run's authorship — pointed at `gh pr diff <pr>`, the lane's §3-confirmed
acceptance criteria, and TASK.md / `.dispatch/progress.md` in the checkout. Its brief: find
correctness bugs, security issues, uncovered acceptance criteria and convention breaks; report each
finding with file, line and severity; answer "no findings" explicitly when there are none. Your own
read of the diff is corroboration, never the review — you already verified this work for §6f, and
the same eyes miss the same things twice.

**2. Fix what it finds, on the lane's own branch.** Prefer the lane's agent when it is still alive —
§6d steering applies, and it holds the context that wrote the code. When the agent has exited or the
finding is a small mechanical fix, apply it yourself in the lane's worktree, commit with an ordinary
conventional message, and push the same explicit refspec §6f used — fixes are part of publishing, so
they ride the same branch, never a second one. Re-run the §6e checks that the fix touches. A lane
still drawing findings after **3 review rounds** stops: record `escalated` with the outstanding
findings, leave the PR open, and surface it — unbounded self-repair is how a lane burns the night on
a disagreement.

**3. Merge only a green, mergeable PR.**

    gh pr checks <pr> --repo <owner/repo>        # all success/skipped; pending → next sweep
    gh pr view <pr> --json state,mergeable       # OPEN and MERGEABLE, or nothing happens

Merge with the repo's own recipe — the §8 block's `gh pr merge <pr> --squash --delete-branch` unless
the repo plainly uses another — then record `merge_sha` and set phase `merged`. A failing check is
never something to force past: red means surface it, and a conflicted PR means rebase the lane
branch onto the fresh base, re-verify §6e, push again, and let the reviewer see the new diff once
more. `--draft` PRs are never auto-merged — they were opened to land quietly, so `gh pr ready` is
the user's call, not yours.

**4. A merged lane's residue is pure cost — clean it on the spot.** The §8.1 offer exists for PRs
the *user* merged; when the run merged the PR itself, that question is already answered. Run §8.1
steps 1–3 for the lane right away — worktree, dead workspaces, `-D` on the squash-merged branch,
empty parent dir — and report the freed disk in §8.

---

## §6i Close the sweep

Rewrite the state file atomically (write `.tmp`, then `mv`). Emit **one line per lane** — lane,
phase, the driver's own status field, `used_pct`, compactions, turn state, PR number or `—` — never
raw JSON. This sweep runs many times; verbose output is what makes a long supervision run
unaffordable.

Escalation-type outcomes are recorded in the state file the first time (`escalated`, with reason).
Later sweeps re-surface them as one report line each, never as a fresh escalation, and §7 counts
such lanes as awaiting-user.

---

## §7 Arm the recurring loop

Unless `--no-loop`, after dispatch invoke the `loop` skill with `5m` and this skill's own `--resume`
invocation (the slash form that actually resolves here — `/dispatch-<agent> --resume`, or the
plugin-qualified `/herdr-dispatch:dispatch-<agent> --resume`), so supervision continues on a timer
without holding the session.

The timer is the **fallback** for a finished lane — that announces itself through the §5b
notify-back — but it is the **only** thing that recovers everything which arrives silently: stalls,
blocked panes, hot lanes needing compaction, a lane that stopped mid-work and needs the next nudge,
a rate limit that parked the agent, and any notify-back that was rejected while this session was
blocked. That is what keeps 5 minutes load-bearing. **The less autonomous the agent, the more the
timer *is* the engine** — the driver's §6c says which regime it is in.

Tell the user in Chinese that it is armed and how to stop it. Each tick is exactly one §6 sweep; a
tick landing right after a notify-back sweep is harmless — sweeps are idempotent. A `--resume` sweep
in a session with no armed loop re-arms it whenever non-terminal lanes remain (unless the run's
recorded flags say `--no-loop`) and re-records `orchestrator_pane` as the current pane — that is how
a run whose original session died gets its supervision back (§2).

`--no-loop` disarms only the timer; the briefs still carry the notify-back, but that signal alone is
lossy — a ring landing while this session is blocked (an open `AskUserQuestion`, a permission
prompt) is rejected as `agent_blocked` and never retried (§5b) — so when the user passed
`--no-loop`, tell them in Chinese that a missed ring is recovered only by re-running this skill with
`--resume` by hand, and that a lane which stops mid-work stays stopped until such a sweep nudges it.

Stop the loop once every lane is terminal or awaiting-user, and say which lanes wait on what.
Terminal means `merged`, `failed`, user-paused, `verified` with a recorded reason why §6f could not
publish it, or `published` when §6j is off the table — `--no-automerge`, `--draft`, `--no-pr`, or a
recorded merge-blocked reason. A `published` lane under the default contract is **not** terminal: it
is mid-§6j, and the loop is what carries it through review to merge. Awaiting-user means a recorded
`escalated` the user has not yet answered — a lane whose work is done but whose branch is still
unpushed is **not** terminal either, and the loop is what eventually gets it out.

Do not busy-wait inside one turn instead: a sweep is cheap, but a blocking sleep loop burns the Bash
tool's ceiling and holds the session hostage.

---

## §8 Report

Per lane: 分支, checkout 路径, 状态, 已完成/剩余清单项, commit 数（§6e 判定粒度过粗的，在这里标注一下）,
**验收标准逐条结果**（每条：通过/未通过/无法机械验证时给依据）, 该 agent 的运行情况（driver 的 §6a
报的状态字段、token/用量、有无暂停 / 限流 / 阻塞经历；驱动方式降级过的写明原因）,
是否偏离已确认的实施计划（有则一句话说明偏在哪、为什么）, compaction 次数,
**PR 链接**（未开成的写明原因，别留空）, **review 与 merge 结果**（merged 的给 merge sha、review
轮数和 §8.1 清掉了什么；没合的写明卡在 §6j 哪一步）.

Name the agent and version once at the top, and say plainly which side of the line each thing is on:
which PRs the run reviewed, fixed and merged itself (§6j), and which it deliberately left open —
`--no-automerge`, `--draft`, escalated after 3 review rounds, or blocked on red checks — with the
reason for each. For every lane left unmerged, print — do not run — the follow-up commands:

    herdr worktree remove --workspace <ws>             # destroys the checkout AND kills its agent process
    gh pr merge <pr-number> --squash --delete-branch   # per lane, after you have reviewed it
    git -C <repo> branch -d <branch>                   # only if the branch outlived the PR merge;
                                                     # a squash-merged branch needs -D — see §8.1

The block is in that order on purpose: `worktree remove` runs **before** `gh pr merge
--delete-branch`, because git refuses to delete a local branch that is still checked out in a
worktree, and the merge command will report a partial success. Warn that `worktree remove` discards
uncommitted work in that checkout, and remember each lane may have **two** workspace ids to clean up
(§4). Only when the run used `--draft`, print `gh pr ready <pr-number>` ahead of the merge command:
GitHub refuses to merge a draft outright (`Pull request is not mergeable: it is in draft state`).

## §8.1 Post-merge cleanup — offer it, don't leave it to memory

(Lanes §6j merged are already clean — it ran this on the spot. This section covers PRs the user
merged by hand, lanes left open by `--no-automerge`/`--draft`/escalation, and runs that predate
§6j.)

The §0 ban on `worktree remove` protects lanes **while the run is live**. Once every PR of the run
is merged (or the run is closed for good), that rationale is gone and the residue becomes pure cost:
each lane's worktree holds a full checkout plus whatever its dependency installs and builds produced
(routinely 1–2 GB per lane), and the branch refs linger after GitHub deletes the remote side. So when
you learn the run's PRs have merged — whether you merged them on the user's instruction or the user
says so — **offer cleanup once, unprompted by anything but the merge**, and on approval run it
yourself rather than printing commands again. The signal can arrive after the loop has stopped: a
`--resume` sweep, or any later session the user tells "those PRs merged", still owes this offer.
Check `gh pr view <pr> --json state` for the live merge state — never trust a state file that last
saw the lane as `published`.

1. `herdr worktree remove --workspace <ws>` per lane workspace recorded in the state file (both ids
   when §4 created two) — this also closes the workspace and deletes the lane's installed
   dependencies and in-checkout build artifacts. If a recorded workspace id no longer resolves, the
   workspace was closed out-of-band; finish the job by path instead:
   `git -C <repo> worktree remove <checkout_path>` when the directory still exists, then
   `git -C <repo> worktree prune` to drop the stale registration when it does not.
2. Branch deletion needs a merge check, not ancestry. §8 merges with `--squash`, and a squash-merged
   branch tip is never an ancestor of the base — `git branch -d` refuses it forever, so "never -D"
   would strand every branch this run published. Per lane branch:

       gh pr list --repo <owner/repo> --head <branch> --state merged --json number

   - a merged PR exists → the work is in the base even though ancestry says otherwise →
     `git -C <repo> branch -D <branch>` is safe.
   - no merged PR, but `git merge-base --is-ancestor <branch> origin/<base>` → `branch -d`.
   - neither → the branch still holds work nobody merged: keep it, and say why in the report.
3. Sweep the residue the state file cannot see. A workspace outlives its checkout: when a lane's
   worktree directory was deleted out-of-band (a manual `rm`, a crashed run, a different session's
   cleanup), the herdr workspace stays behind pointing at nothing. List workspaces, `test -d` each
   `checkout_path`, and `herdr workspace close` the ones whose path is gone — a workspace with no
   checkout can only dead-end, so closing it destroys nothing. Then `rmdir` the lane's empty parent
   directory under `~/.herdr/worktrees/<repo>/`: it survives every `worktree remove` and collects
   one stale entry per repo otherwise.
4. Verify with `git -C <repo> worktree list` that only worktrees belonging to other runs remain, and
   report the disk freed (`du -sh` before/after is one line each).

Keep, never delete: the run's state directory (`~/.claude/<skill-name>/<run-id>/` — the audit trail
of what was verified and pushed, and tiny) and any shared caches (Xcode DerivedData, pnpm store) that
predate the run. The agent's on-disk chat transcripts (e.g. `~/.cursor/chats/<hash>/<uuid>` for
cursor, the driver says where its agent writes) are the one judgement call: they are the only full
record of *why* a lane decided what it did, so default to a grace period — offer to delete them a few
days after merge if no regression has surfaced, not immediately. If the user wants them gone now, they
go now.

Cleanup order still matters: worktrees first, branches second, for the same reason as the block
above.
