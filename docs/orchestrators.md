# Running the dispatchers under other orchestrators

All nine dispatch skills use the same omp lane runtime and local magpie routing policy. Eight
names select models; `dispatch-omp` accepts a model ID or a user-supplied exact magpie catalog selector.
The host orchestrator loads the skill, plans and supervises lanes, verifies acceptance criteria, and owns
publication, independent review, fixes, merge, and scoped post-merge cleanup by default. It does not
change the lane runtime by choosing a different preset.

Runtime smoke on omp 18.15.0 verified Herdr launch, a magpie-backed goal creating and reading a
file, goal completion metadata, exact-file restore, and scout/sonic child requests using magpie
under a run-scoped overlay. The catalog exposed only magpie with that overlay. This does not claim
a full worktree-to-GitHub publication run, compaction under pressure, or every upstream route was tested.

On omp 18.16.0, isolated print-mode tasks verified real read/write/read tool exchanges through
the GPT-6 Astra auto group and the sole exposed DeepSeek V4.1 Flash entry. Artifacts matched
the input nonce and computed total; session-matched magpie usage confirmed the served model
and HTTP 200 without a model swap. GLM reached its catalog route but failed on insufficient
upstream balance. Launch success therefore requires a successful model/tool exchange with
matching response metadata, not just catalog presence or a created session. Full Herdr goal
and publication lifecycle coverage remains as described above.

## Host capabilities

The host must be able to load `SKILL.md` and all five shared references, run shell commands, and
operate inside the caller's herdr pane (classic) or herdr-core terminal (`hc`). Dispatch detects the
backend in entry §1 and records it as `mux`: herdr panes are created through `herdr worktree create`
and `herdr agent start`; hc lanes run as `hc run --outlive-parent --keep` child terminals with
`dispatch.*` labels, whose status notes reach the orchestrator automatically. A dispatch request
authorizes routine lane grouping and
creation of the task's worktrees, workspaces and terminals. Present the concrete plan, then proceed
without lane/pane confirmation. Ask only about unresolved scope or material choices that require
the user's decision; honor an explicit request to review the plan before execution.

Claude-style `allowed-tools` frontmatter is not a portable permission guarantee. Check how the
installed host treats it and whether the required multiplexer (`herdr` or `hc`), git, omp, jq,
python3, and optional gh
operations can run with the requested approval posture. Do not infer support from a host name or
silently weaken the requested approval policy.

Every model invocation under the dispatch workflow, including all omp model roles and delegated
subagents, must use an explicit `magpie/...` route. A non-magpie host configuration is not a reason
to let lane subagents inherit a different provider. The shared driver scopes routing to run or lane
configuration: it enables only magpie, disables model fallback, and pins model roles and task agent
model overrides. It never changes global host or omp settings.

Model selection must follow the shared routing reference: presets never select a supplier. Resolve
the model to its existing magpie group, or the sole catalog entry if no group exists. Multiple
supplier entries without an unambiguous model group block dispatch; do not choose a supplier or
alter magpie configuration. Model/version ambiguity is distinct from supplier routing. Honor any
user-supplied exact `--model magpie/...` chat selector, including supplier entries; the skill must
not infer that preference itself. If magpie exposes a model absent from omp's catalog, refresh
once using the launch overlay and diagnose any remaining adapter mismatch before declaring it unavailable.

## Shared references and packaging

Every `skills/dispatch-*/references/` directory exposes these symlinks:

| Reference | Source |
| --- | --- |
| `entry.md` | `../../_shared/entry.md` |
| `routing.md` | `../../_shared/routing.md` |
| `driver.md` | `../../_shared/driver.md` |
| `plan.md` | `../../_shared/plan.md` |
| `supervise.md` | `../../_shared/supervise.md` |

Installing the whole repository preserves the relative links. Copying only one skill requires
dereferencing all five references so they remain readable without a sibling `_shared/` directory.
A skill with missing references is incomplete and must not dispatch work.

### Claude Code

Install through the repository marketplace as described in the [README](../README.md), or launch
Claude Code with `--plugin-dir` for a local checkout. The plugin-qualified skill name is, for
example, `herdr-dispatch:dispatch-omp`. Confirm that the installed skill can read every reference.

Do not assume that a `loop` skill or timer API exists merely because the host is Claude Code.
Detect the capabilities in the active session before arming supervision.

### Codex

The repository provides `.codex-plugin/plugin.json` with `"skills": "./skills/"`. Use the installed
Codex version's plugin interface to add this repository and enable `herdr-dispatch`. Skill invocation
may be model-driven: ask Codex to use `herdr-dispatch:dispatch-omp` with the desired `--model` and
task text if the host does not expose the skill as a slash command.

Some Codex plugin caches omit symlinks when copying the repository. The plugin's `SessionStart`
command hook copies **all five** shared files—`entry.md`, `routing.md`, `driver.md`, `plan.md`, and
`supervise.md`—into each cached `dispatch-*/references/` directory, including `dispatch-omp`.
Missing reference directories are recreated. Existing valid symlinks remain shared references;
regular copies are refreshed on session start. A broken link or copy failure makes the hook fail.

If the installed host does not run plugin hooks, materialize the references in the selected plugin
cache version before using a skill. Set `dispatch_skills` to that version's absolute `skills`
directory and run:

```bash
(
  [ -d "${dispatch_skills:?Set dispatch_skills to the selected cache skills directory}/_shared" ] || exit 1
  for skill_dir in "$dispatch_skills"/dispatch-*; do
    [ -f "$skill_dir/SKILL.md" ] || continue
    mkdir -p "$skill_dir/references" || exit 1
    for reference in entry routing driver plan supervise; do
      if [ -L "$skill_dir/references/$reference.md" ]; then
        [ -f "$skill_dir/references/$reference.md" ] || exit 1
        continue
      fi
      cp "$dispatch_skills/_shared/$reference.md" "$skill_dir/references/$reference.md" || exit 1
    done
  done
)
```

Check the active Codex session for an actual recurring-prompt facility. A desktop automation API,
a queue command, or an ability to send a prompt once does not establish that a CLI scheduler exists.
Do not assume a native timer or install a scheduler to fill the gap.

### Other skill-capable hosts

A host such as Kimi can load the same entry points if its installed version supports this skill
format and the shell and confirmation requirements above. Follow that host's skill installation
interface, preserving or materializing every shared reference. Treat timer APIs such as `CronCreate`
as available only when they are actually exposed with known semantics in the current session.
No current runtime compatibility claim is made solely from earlier native-agent tests.

## Supervision timers

A timer is optional. A sweep is the unit of supervision, and it always names an exact skill and
run ID:

```
Use dispatch-codex --resume --run <id> to perform one supervision sweep.
```

When a recurring timer is present, use its supported API, record its identity and lifecycle, and
cancel the run's timer when all lanes are terminal or awaiting the user. Respect `--no-loop`. Do not
invent tool names, cron commands, scheduled-task APIs, or assumptions about session lifetime.

When no timer is available, report that supervision requires a manual resume and print the exact
skill and `--run <id>` command. An existing external scheduler may be used only when its capability
and authorization are established; do not install one, mutate global scheduler configuration, or
claim that the run will keep supervising itself. Any authorized external mechanism must target the
recorded run and stop when it is gone or all its lanes are terminal or awaiting the user.

Terminal states follow shared supervision §7: `merged`, `failed`, user-paused, or `verified` with a
recorded publication blocker. `published` is terminal only under `--no-automerge`, `--draft`,
`--no-pr`, or a recorded merge blocker. Otherwise a published PR still needs review and merge.
An unanswered recorded `escalated` outcome awaits the user. Completed but unpushed work is not
terminal without a recorded blocker.

## Persistent state and resume

Every host uses `~/.claude/<skill>/<run>/state.json`. A compatible state has `schema_version: 2`,
`agent_kind: "omp"`, and explicit per-lane `model`, `thinking`, `role_models`, `session_directory`,
`session_file`, `session`, and `runtime_config` fields, plus Herdr `session_identity` when present.
The lane's worktree, branch, and pane identity must also match before it receives input.

A resume rereads state from disk and uses those recorded routes and sessions. `--run <id>` selects
an exact run within the invoked skill's namespace; omitting it is safe only when the repository
match is unambiguous. A preset name never substitutes for a recorded model or session path.

Reject legacy schemas/runtimes without mutation: do not rewrite state, relaunch old agents, steer
their panes, or move their branches. Version-2 prepared lanes may legitimately have null session
fields before first launch; reconcile their recorded launch state with the pane before proceeding.
Missing identity for a previously running lane is a blocker, never permission to guess a session.

## Acceptance, publication, and cleanup

Changing the host does not change the workflow boundaries. Every lane retains its own worktree,
recorded plan, and acceptance criteria. A `DONE` marker is a claim; the orchestrator independently
verifies the criteria, clean tree, and real commits before publication. Agents never push, open
PRs, or merge; the orchestrator owns these actions. Missing origin or gh credentials produce
explicit local-only or PR-creation blockers rather than fabricated success. Never force-push,
push the base branch, or publish an unrecorded branch.

The default contract follows [shared supervision §6j](../skills/_shared/supervise.md): independently
review each PR with a fresh omp reviewer in a separately recorded pane/session, using the same
magpie-only routing overlay. Fix findings on the lane branch, reverify affected criteria, push the
same branch and repeat review. After three rounds with unresolved findings, record `escalated` and
leave the PR open. Merge only when the PR is open and mergeable and all checks are successful or
skipped; pending checks wait, and failing checks or merge blockers are surfaced. Changed diffs need
renewed verification and review. Record the review rounds, findings, and merge SHA.

`--no-automerge` leaves ready PRs for the user; `--draft` and `--no-pr` also opt out of automatic
review and merge. Draft PRs are never marked ready automatically. For lanes left unmerged, print
the follow-up commands, including `gh pr ready` for draft runs, instead of executing them.

When the run merges a lane, immediately execute the scoped post-merge cleanup in §8.1: remove the
recorded worktree and its workspaces, delete the eligible branch, close the run's dead workspaces,
and remove its empty worktree parent. Remove worktrees before deleting branches. A confirmed
merged PR permits `branch -D` after squash merge; otherwise require ancestry for `branch -d`, or
keep the branch and report why. If a workspace ID is missing, use the recorded checkout path and
the stale-registration procedure in §8.1. Keep unrelated resources intact.

For PRs merged manually or runs closed outside that path, offer cleanup once and execute it after
approval, checking live PR merge state first. Preserve run state and preexisting shared caches.
Keep chat transcripts for a grace period unless the user requests earlier deletion. Verify scoped
cleanup and report the disk freed, as §8.1 requires. The final report distinguishes PRs the run
reviewed and merged from those left open, with their blockers and the cleanup performed. These
rules apply to every route preset and to `dispatch-omp`.
