# herdr-dispatch

Dispatch coding work into isolated [herdr](https://herdr.dev) worktrees, execute every lane with
**omp**, and route every model request through the local **magpie** provider.

The eight existing dispatch names are model presets. They share one runtime and one
supervision protocol. `/dispatch-omp --model <model-id>` selects a model without a preset.
Skills choose models; magpie chooses their suppliers, accounts, and failover policy.
The orchestrator plans the lanes, checks their acceptance criteria, publishes verified branches,
and by default carries their PRs through independent review, fixes, merge, and scoped post-merge
cleanup. Lane agents never push, open PRs, or merge.

## Requirements

| What | Why |
| --- | --- |
| **herdr or herdr-core** | A classic herdr pane (`HERDR_ENV=1`, `herdr` CLI) or a herdr-core terminal (`HC_TERMINAL_ID`, `hc` CLI). Creates and controls the isolated worktrees and lane terminals. Dispatch refuses to run outside both. |
| **A git repository** | Run from the main checkout; every lane gets a linked worktree based on a recorded base ref. |
| **omp** | The only lane runtime. It must be resolvable from each lane terminal's launch environment and support the launch, session, and routing capabilities required by the shared driver. |
| **Local magpie routes** | Selected models must exist in the local catalog and be accessible through omp's `magpie` provider. Every model role and delegated subagent must use an explicit `magpie/...` route. |
| **`python3`, `jq`** | Inspect persisted run and session state. |
| **`gh`, authenticated** | Optional. Without it, verified branches can be pushed and a PR command is printed for you. |
| **`origin` remote** | Optional. Without it, lanes stay local with a recorded publication blocker. |

Preflight checks the installed capabilities and requested routes before creating lanes. Missing omp
support or an unavailable route is a blocker, not a reason to launch a different runtime or silently
choose another provider. The skills do not install tools, authenticate accounts, or mutate global
model configuration.

## Installation

In Claude Code:

```
/plugin marketplace add bestony/herdr-dispatch
/plugin install herdr-dispatch@herdr-dispatch
```

If the install summary asks you to run `/reload-plugins`, do so.

The nine skills can also be installed through [skills.sh](https://skills.sh):

```bash
npx skills add bestony/herdr-dispatch --list
npx skills add bestony/herdr-dispatch
npx skills add bestony/herdr-dispatch -g
npx skills add bestony/herdr-dispatch -s dispatch-omp -a claude-code -y
```

Each installed skill needs its five shared reference files. Installers that copy one skill must
dereference its `references/` symlinks; preserving those links without the sibling `_shared/`
directory leaves an incomplete installation. The Codex plugin includes a session-start hook to
materialize all five files in its plugin cache. See [other orchestrators](docs/orchestrators.md).

For local development:

```bash
git clone https://github.com/bestony/herdr-dispatch.git
claude --plugin-dir ./herdr-dispatch
```

Run `/reload-plugins` after edits.

## Quick start

Start the orchestrator inside a herdr pane or a herdr-core (`hc`) terminal, in the repository's main checkout:

```
/dispatch-codex Add an owner filter to the repos list; fix the websocket reconnect timeout
```

To select a model directly, use `/dispatch-omp --model gpt-6-astra` followed by your task text.
The skill resolves that model through magpie's live catalog, preferring its existing routing group.

1. Preflight checks the multiplexer backend (herdr or hc), omp, routes, the repository, and
   publication capabilities, then selects
   the base ref and fetches `origin` when available.
2. The orchestrator groups tasks into lanes with high cohesion within each lane and low coupling
   between lanes. Quality comes first: independent outcomes run concurrently within the lane cap;
   work requiring shared edits or intermediate handoffs stays together. It writes a concrete
   implementation plan and acceptance criteria using the repository's actual check commands.
3. It presents the lane table, model and thinking choices, plans, acceptance criteria, and approval
   posture as an informational update, then proceeds without lane/pane confirmation. It asks only
   about unresolved scope or material choices that require your decision, or if you requested plan review.
4. Each lane gets a worktree, a terminal (a herdr workspace+pane or one `hc run` child), an omp
   session, and its own brief as an omp goal.
   Explicit model and role routes are recorded with the session identity.
5. Lanes implement and self-check. The top-level dispatch session owns final acceptance: its
   supervision sweep reads persisted state, checks live identity, continues stopped work when
   appropriate, and independently verifies any lane claiming completion.
6. Verified lanes are pushed on their own branches and opened as pull requests, subject to the
   selected flags and available publication credentials.
7. By default, an independent reviewer examines each PR the run opened. The orchestrator fixes
   findings on the lane branch, reverifies affected criteria, and merges only when checks are green
   and the PR is mergeable, then cleans that lane's recorded worktree and eligible branch.

Recurring supervision is enabled only when the orchestrator actually exposes a suitable timer.
Without one, the report gives the exact command for a manual sweep. No scheduler is invented or
installed. Plans, questions, and reports are in Chinese; briefs, commits, and PR bodies are in English.

## Dispatch names and models

| Skill | Model selection (no supplier preference) |
| --- | --- |
| `/dispatch-codex` | `gpt-6-astra` |
| `/dispatch-glm` | Distinct GLM model identities from the live magpie catalog |
| `/dispatch-mimo` | Distinct MiMo model identities from the live magpie catalog |
| `/dispatch-deepseek` | `deepseek-v4.1-flash` |
| `/dispatch-grok` | `grok-4.7@500k` |
| `/dispatch-opencode` | `deepseek-v4.1-flash`, the same model as `dispatch-deepseek` |
| `/dispatch-cursor` | `claude-opus-5-5@1m` |
| `/dispatch-devin` | `swe-2` |
| `/dispatch-omp` | Generic entry; requires an explicit `--model <model-id>` or exact magpie catalog selector |

The preset mappings live in [the shared routing reference](skills/_shared/routing.md). All nine
entries execute omp. The names do not select native Codex, GLM, Mimo, DeepSeek, Grok, OpenCode,
Cursor, or Devin CLIs or suppliers. An unavailable exact model blocks lane creation. For GLM and
MiMo, one distinct model is selected, several require a model/version choice, and zero is a blocker.
An explicit available `--model` overrides any preset; the live magpie catalog decides availability.

For the selected model, use its existing magpie routing group when available. If magpie exposes
only one supplier entry and no group, that sole entry resolves the model without a supplier preference.
Multiple supplier entries without an unambiguous model group are a magpie configuration blocker;
dispatch never picks a supplier or changes routing configuration. A user-supplied exact magpie
catalog selector is honored, including an individual supplier entry; the skill never invents such
a preference itself. Explicit group selectors delegate delivery to the group's policy.
If magpie exposes a model missing from omp, refresh omp's catalog once under the launch overlay
before reporting an adapter/catalog mismatch. Full details are in the shared routing reference.

Routing covers the lane model, all model roles, and every delegated subagent. Persisted routes are
explicit and stay within magpie; neither global defaults nor an unrelated provider may supply a
silent fallback. A run-scoped configuration overlay enables only magpie, disables model fallback,
and pins every model role and task agent model override. It never changes global settings.
Plugin-qualified names also work where supported, such as `/herdr-dispatch:dispatch-codex`.

## Flags

```
/dispatch-<preset> <task-1>; <task-2>; … [flags]
/dispatch-omp --model <model-id> <tasks> [flags]
```

Everything that is not a flag is task text. Tasks split on numbered items, newlines, or `;`.

| Flag | Meaning | Default |
| --- | --- | --- |
| `--model <model-id>` | Model identity resolved through magpie, or any exact magpie chat selector explicitly supplied by the user | Preset model; required for `dispatch-omp` |
| `--thinking <level>` | Explicit omp thinking setting; unsupported choices are rejected | `high` when supported, otherwise a catalog-supported level, recorded per lane |
| `--lanes N` | Cap on concurrent lanes, 1–16 | `16` |
| `--base <ref>` | Base ref for lane branches | `origin/<current>` if available, else the current branch |
| `--no-yolo` | Explicitly pass omp `--approval-mode always-ask`; unsupported approval controls are a preflight blocker | off |
| `--yolo` | Request the default unattended approval posture, subject to omp capability checks | on |
| `--draft` | Open draft PRs and opt out of automatic review/merge; marking ready remains your choice | off |
| `--no-pr` | Push verified lanes and print the PR command; no automatic review/merge | off |
| `--no-automerge` | Publish ready PRs, then leave review and merge to you | off — independent review, fixes, merge, and scoped cleanup are the default |
| `--resume` | Skip planning and run one supervision sweep over an existing compatible run | off |
| `--run <id>` | Select a specific run for resume, within this skill's state namespace | Resolve from recorded repository identity only when unambiguous |
| `--no-loop` | Do not arm a recurring supervision timer | off |

Worktree isolation has no opt-out: `--no-worktree` is rejected before creation. Approval flags must
map to capabilities actually offered by the installed omp version; native-agent permission flags
are not reused. An inability to enforce the requested approval posture is reported before dispatch.

omp handles context compaction automatically. The legacy `--compact-at` option is no longer supported.

## Resuming and stopping

A resume command names the skill that created the run and preferably its exact run ID:

```
/dispatch-codex --resume --run <id>
/dispatch-omp --resume --run <id> --no-loop
```

The state file is the source of truth, and every sweep rereads it. With no `--run`, selection must
be unambiguous for the current repository; it must never pick an arbitrary run. Resuming uses the
recorded lane routes and session identities rather than reconstructing them from a preset name or
conversation memory.

A timer, when available, must target the exact skill and run ID. Its lifetime and cancellation
behavior come from the detected scheduler. Stop it when every lane is terminal or awaiting the
user. Terminal means `merged`, `failed`, user-paused, or `verified` with a recorded publication
blocker. `published` is terminal only with `--no-automerge`, `--draft`, `--no-pr`, or a recorded
merge blocker; otherwise supervision continues through review and merge. An unanswered recorded
`escalated` outcome awaits the user. A completed but unpushed branch is not terminal without a
recorded blocker. A session ending may leave lanes running without supervision; resume restores
supervision only through supported capabilities.

**Legacy runs are rejected without mutation.** A run without `schema_version: 2` or with a different
`agent_kind` is not upgraded or steered. Its files, terminals, sessions and branches remain untouched.
Version-2 prepared lanes can have null session fields until launch; a running lane with missing
identity is blocked until reconciled, never attached to a guessed session.

## What a run leaves on disk

Run state lives at `~/.claude/<skill>/<run>/state.json`, including when another supported host is the
orchestrator. `<skill>` is the invoked name, such as `dispatch-codex` or `dispatch-omp`.

Each state file has `schema_version: 2` and `agent_kind: "omp"`. Each lane records its explicit
`model`, `thinking`, `role_models`, `session_file`, `session_directory`, `session` (the session
header ID), and `runtime_config`, plus Herdr `session_identity` when present. It also records the
multiplexer backend (`mux`), repository, worktree, branch, terminal, and progress identity. Session paths are recorded from the
actual runtime and checked before any steering; a reused lane name is insufficient evidence.
State updates are atomic.

Each lane checkout contains a git-excluded `.dispatch/` directory:

- `TASK.md`: objective, recorded plan, checklist, acceptance criteria, and boundaries.
- `progress.md`: the lane's persisted progress, used when continuing work.
- `DONE`: the lane's claim that every criterion holds.

Run artifacts also include PR bodies written to files to preserve multiline content. `DONE` is a
claim, not acceptance: the orchestrator reruns the recorded criteria before publication.

## Publication, review, and cleanup

These invariants apply to every preset and to `dispatch-omp`:

- Never force-push, push the base branch, or push a branch absent from the run state.
- Lanes never push, open PRs, or merge. A lane requesting publication is reported rather than
  granted permission; the orchestrator owns publication after verification.
- Completion requires a clean tree, real commits, and independently verified acceptance criteria.
- Never steer a session or terminal without checking it against the recorded identity.
- Review and merge only PRs this run opened. Independent review uses a fresh omp session in a
  separately recorded terminal, with a magpie-only overlay and no share in the code's authorship.
- Preserve live lanes, unrelated workspaces/terminals and branches, the run's state directory, shared caches,
  and chat transcripts. Cleanup is scoped to the run and its confirmed lifecycle state.

The default lifecycle continues after publication. A fresh reviewer checks correctness, security,
acceptance coverage, and conventions. Findings are fixed on the lane's existing branch, affected
acceptance checks are rerun, and the same branch is pushed without force. After three review rounds
with unresolved findings, record `escalated`, leave the PR open, and report the findings.

Merge only an open, mergeable PR with all checks successful or skipped. Pending checks wait for the
next sweep; failing checks and merge blockers are surfaced. Resolve conflicts on the lane branch,
reverify, and obtain review of the updated diff without bypassing the push rules. Use the repo's
merge recipe, normally squash merge with remote branch deletion, and record the merge SHA.
`--no-automerge`, `--draft`, and `--no-pr` opt out of this automatic review/merge path; draft PRs are
never marked ready automatically.

After each test/check, and when a lane becomes terminal (including failed, paused, or
`--no-automerge`), clean its no-longer-needed runtime resources using the launch records and
identity checks in [supervise.md §8.2](skills/_shared/supervise.md). Preserve active work and shared
resources; path scans are read-only discovery, never authority to stop a process. Keep the resource
ledger outside the checkout and retain stopped records. This cleanup is independent of merging.
After the run merges a lane, immediately perform the scoped cleanup in
[supervise.md §8.1](skills/_shared/supervise.md): check runtime resources under §8.2, then remove its
recorded worktree and workspaces/terminal,
delete the eligible local branch, close its dead workspaces, and remove its empty worktree parent.
Worktrees come before branch deletion. A branch with a confirmed merged PR may need `branch -D`
after squash merge; without a merged PR, use `branch -d` only when ancestry proves it merged, and
otherwise keep it. Missing workspace/terminal IDs require the recorded checkout-path cleanup and stale
worktree-registration handling described in §8.1. Never clean unrelated resources.

For PRs merged manually or runs closed outside that default path, offer post-merge cleanup once;
after approval, check live PR merge state and execute the same scoped procedure. Preserve the run
state as the audit trail and shared caches that predate the run. Keep chat transcripts by default,
offering deletion after a grace period unless the user explicitly requests it sooner.

For lanes left unmerged, the final report prints follow-up commands instead of running them:

```bash
herdr worktree remove --workspace <ws>                          # herdr backend
hc kill <t>; git -C <repo> worktree remove <checkout>; hc rm <t>  # hc backend
gh pr merge <pr-number> --squash --delete-branch
git -C <repo> branch -d <branch>
```

For draft runs, print `gh pr ready <pr-number>` before the merge command. Explain that worktree
removal destroys the checkout, stops its agent, and discards uncommitted work; identify both recorded
workspace IDs when herdr created two, or the recorded terminal on hc. Note the squash-merge branch-deletion rule above. The report
distinguishes PRs reviewed and merged by the run from those left open, records review rounds,
findings, merge SHAs and blockers, and lists cleanup performed and disk freed.

## Repository layout

```
.claude-plugin/
├── plugin.json
└── marketplace.json
.codex-plugin/
└── plugin.json                  # materializes all five shared references in the plugin cache
skills/
├── _shared/
│   ├── entry.md                 # entry, flags, capability gates, state contract
│   ├── routing.md               # magpie routes, roles, and model availability
│   ├── driver.md                # common omp launch and session protocol
│   ├── plan.md                  # lane plans, worktrees, briefs, and bookkeeping
│   └── supervise.md             # resume, acceptance, publication, timer, and report
├── dispatch-omp/                # generic explicit-model entry
├── dispatch-codex/
├── dispatch-glm/
├── dispatch-mimo/
├── dispatch-deepseek/
├── dispatch-grok/
├── dispatch-opencode/
├── dispatch-cursor/
└── dispatch-devin/
```

Every dispatch directory contains a `SKILL.md` entry and a `references/` directory with five
symlinks: `entry.md`, `routing.md`, `driver.md`, `plan.md`, and `supervise.md`, each pointing to
`../../_shared/<name>.md`. Shared behavior and the omp driver have one source; presets select
models while magpie owns supplier routing.

## Verification status

Partial runtime smoke is recorded, not a full dispatch run. On omp 18.15.0 the shared driver
exercised Herdr launch through local magpie, a magpie-backed goal creating and reading a file, goal
completion metadata, exact-file restore, and scout/sonic child inference under a run-scoped overlay.
A full worktree-to-PR run, supervision under compaction pressure, and every upstream route remain
unverified; historical tests of the native-agent dispatchers do not cover this runtime. Re-read
`omp --version` and the installed CLI help before relying on flags on another version. See
[orchestrator integration notes](docs/orchestrators.md) for packaging and capability requirements.

On omp 18.16.0, model-resolution checks covered group precedence, supplier/group ambiguity,
family deduplication, variant preservation, and a same-overlay catalog refresh. Actual isolated
`omp --print` tasks then read an input file, computed a total, wrote a result, and read it back
through `magpie/auto/gpt-6-astra` and the sole exposed DeepSeek V4.1 Flash entry. Both results
were correct; session metadata and session-matched magpie usage records showed HTTP 200,
the expected served model, and `swapped=false`. A GLM attempt reached its exposed route but
failed with an upstream insufficient-balance error; catalog presence alone is not runtime success.
These checks verify model delivery and tool execution, not a complete Herdr goal-to-PR lifecycle.

## License

MIT — see [LICENSE](LICENSE).
