# Model routing through local magpie

The installed catalog is authoritative. Run `omp --version`, `magpie healthcheck`, and `omp models magpie --json` before creating worktrees. The JSON has a `models` array with `provider`, `selector`, `id`, `thinking`, `contextWindow`, and `input`. Require provider `magpie`, kind `chat`, and an exact selector match; fuzzy CLI matching is forbidden. A healthy gateway and catalog entry do not prove inference works: the first lane turn must show a successful assistant/tool exchange before the route is considered exercised.

## Presets

| Entry | Preferred selector | Candidate filter if preferred is absent |
| --- | --- | --- |
| dispatch-omp | none; require --model | none |
| dispatch-codex | magpie/codex/gpt-6-astra | id starts with codex/ |
| dispatch-cursor | magpie/cursor/claude-opus-5-5@1m | id starts with cursor/ |
| dispatch-devin | magpie/devin/swe-2 | id starts with devin/ |
| dispatch-grok | magpie/grok/grok-4.7@500k | id starts with grok/ |
| dispatch-opencode | magpie/opencode-go/deepseek-v4.1-flash | id starts with opencode-go/ or opencode/ |
| dispatch-deepseek | magpie/opencode-go/deepseek-v4.1-flash | final model component contains deepseek, case insensitive |
| dispatch-glm | no assumed subscription or slug | final model component contains glm, case insensitive |
| dispatch-mimo | no assumed subscription or slug | final model component contains mimo, case insensitive |

Explicit `--model` wins over the preset, but must still be an exact `magpie/...` catalog entry. Without it, use the preferred selector only if present; otherwise accept exactly one filtered candidate. Zero candidates: stop before creating resources, explain the missing magpie route/subscription and show `omp models magpie --json`. Multiple candidates: present exact selectors and ask which to use. Do not choose the first item, subscribe, edit providers, or replace a missing family with another model. GLM/MiMo entries stay installed and become usable as soon as the catalog exposes their routes.

Thinking: validate explicit levels against the selected entry's `thinking` list (`off` for a non-reasoning model). Without an override choose `high` if offered, otherwise `medium`, then `low`, then the first advertised level; non-reasoning models use `off`. Record the result rather than inheriting a machine-wide effort. Avoid `auto`, which can invoke an extra judgment model. Record the catalog context window for diagnostics; it does not itself measure live context use.

## Per-lane runtime overlay

Write `<run-dir>/<lane>-omp.yml` outside the worktree, with no credentials. Pass its absolute path through `--config` on fresh launch and every restore. Record it as `runtime_config`. Never use `magpie <agent> <model>` or `omp config set` here: those mutate shared settings.

Inspect `omp config list --json`, `omp config get modelRoles --json` and `omp agents --help` on the installed version. Construct the overlay with the selected full selector for **every existing modelRoles key**, plus `default`, `smol`, `slow`, `plan`, `judge`, `advisor`, and `commit`. Record these as `role_models`. Enumerate available agent definitions and existing `task.agentModelOverrides`; override each agent's model with that same selector, including custom agents. Disable per-call model selection. A model choice in a child must not escape through an agent definition, prewalk, advisor, fallback or an inherited role.

The overlay uses these observed omp settings (nested YAML maps):

```yaml
enabledProviders: [magpie]
retry:
  modelFallback: false
  usageAwareFallback: false
autoResume: false
prewalk:
  enabled: false
  auto: false
advisor:
  enabled: false
task:
  perCallModel: "off"
  prewalk: false
compaction:
  enabled: true
  methodOrder: [snapcompact, handoff, shake, soft]
```

Add the generated `modelRoles`, `task.agentModelOverrides`, `task.agentPrewalk` (false for each agent), and `task.agentAdvisor` (false for each agent). Quote strings such as `off` when serializing YAML. Preserve other unrelated settings; do not copy credentials into this file. Remote compaction endpoints are excluded so context maintenance cannot bypass magpie. Disable or explicitly route custom extensions/remote memory services which independently issue model requests; if their routing cannot be established, do not enable them in a dispatch lane. Use `--no-extensions` for an unreviewed installation, documenting that Herdr may then identify the session only by the run-owned session directory (§6a).

Check the effective catalog with `omp models --config <overlay> --json`: every enabled chat model must be a magpie selector. Check the lane transcript's model_change and model_usage metadata and child transcripts during supervision; an unexpected provider is a routing violation, not permission to silently fall back. Stop steering, record it and diagnose the overlay before continuing. Provider filtering is an inference configuration boundary, not a network sandbox; arbitrary project scripts and third-party tools are not model routing controls.

Magpie may itself route a group or fail over upstreams. Preserve the requested magpie selector and report it as a route, not a promise that one physical upstream served every request. Provider/model balancing belongs to magpie, not the dispatch supervisor.
