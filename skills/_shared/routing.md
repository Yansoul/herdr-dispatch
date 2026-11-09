# Model routing through local magpie

The installed catalog is authoritative. Run `omp --version`, `magpie healthcheck`, `magpie models`, `magpie groups`, and `omp models magpie --json` before creating worktrees. The JSON has a `models` array with `provider`, `selector`, `id`, `thinking`, `contextWindow`, and `input`. Require provider `magpie`, kind `chat`, and an exact selector match after resolving the requested model below; fuzzy CLI matching is forbidden. A healthy gateway and catalog entry do not prove inference works: the first lane turn must show a successful assistant/tool exchange before the route is considered exercised.

Before declaring a requested model unavailable, compare `magpie models` with the omp catalog under the same overlay used for launch. If magpie exposes it but omp does not, run `omp models refresh --config <overlay> --no-extensions` once, then re-read `omp models magpie --config <overlay> --no-extensions --json` and resolve again. A remaining mismatch is a catalog/adapter integration failure, not proof that magpie lacks the model. Report the two observed IDs and the exact failure. A model listed only as hidden/not exposed is distinct from an exposed route; do not silently enable it or change magpie settings.

## Model presets and magpie resolution

Skills choose a model identity. Magpie owns supplier selection, account selection, balancing, and failover. The omp provider `magpie` identifies the gateway; a downstream supplier prefix is not a model preference. Historical skill names never constrain suppliers.

| Entry | Requested model | Selection when no exact model is prescribed |
| --- | --- | --- |
| dispatch-omp | explicit --model required | none |
| dispatch-codex | gpt-6-astra | none |
| dispatch-cursor | claude-opus-5-5@1m | none |
| dispatch-devin | swe-2 | none |
| dispatch-grok | grok-4.7@500k | none |
| dispatch-opencode | deepseek-v4.1-flash | none |
| dispatch-deepseek | deepseek-v4.1-flash | none |
| dispatch-glm | resolve from available model identities | final model component contains glm, case insensitive |
| dispatch-mimo | resolve from available model identities | final model component contains mimo, case insensitive |

`dispatch-opencode` and `dispatch-deepseek` intentionally request the same model. This does not select OpenCode or any other supplier. GLM/MiMo also have no supplier preference.

Resolve in two stages before writing the lane overlay:

1. **Choose the model.** `--model <model-id>` overrides the preset. Preserve the complete model ID, including context/variant suffixes such as `@1m`; do not treat another variant or version as equivalent. Remove only the routing namespace when identifying supplier entries, preserving model IDs that themselves contain `/`. Use magpie's catalog/group metadata to establish identity; do not infer aliases from similar display names. Deduplicate the same model across suppliers and its routing group before applying family filters. For a family preset, one distinct model is selected, zero is an availability blocker, and several require asking which model/version the user wants. An unavailable exact model is a blocker, never permission to choose another model from the same supplier.
2. **Let magpie resolve delivery.** Use the existing magpie-managed group for that model when exposed to omp. Inspect `magpie groups` and `magpie group <id>` to confirm membership; do not fabricate an `auto/<model>` or `group/<id>` selector or assume a custom group serves one model by its name. A verified single-model group takes precedence over individual supplier entries. If no such group exists and magpie exposes exactly one selector for that model, use that sole catalog entry without a supplier preference; re-resolve on each fresh run. If several supplier entries exist without one unambiguous model group, report the missing magpie routing configuration. Do not choose the first supplier, rank providers, or ask the user to choose a supplier inside dispatch. Multiple eligible groups also require an explicit magpie group selection; do not invent a priority between them.

`--model` also accepts any exact `magpie/...` chat selector present in the live catalog when the user explicitly supplies it, including a supplier-qualified entry or a managed group. Preserve that explicit request; do not reject a working catalog entry merely because its namespace names a supplier, and do not replace it with a group behind the user's back. Group selection delegates delivery to the group's configured policy, including mixed-model groups when explicitly selected. The skill must never invent a supplier-qualified override from a model name or preset. Do not create/change groups, expose hidden models, subscribe, edit providers, or mutate magpie settings to make dispatch work.

Record the resolved full selector in `model` and use it for every role and child. For example, when the catalog and group metadata expose `magpie/auto/gpt-6-astra`, a request for `gpt-6-astra` uses that group even if individual supplier entries are present. If magpie exposes only one GLM model through one supplier, its selector is a catalog resolution result, never a hard-coded GLM provider preference.

Thinking: validate explicit levels against the selected entry's `thinking` list. Treat a null/missing list on a non-reasoning model as no reasoning levels and use `off`; never iterate null or reject that otherwise valid model. Without an override choose `high` if offered, otherwise `medium`, then `low`, then the first advertised level; non-reasoning models use `off`. A reasoning model with missing level metadata needs capability diagnosis rather than an invented level. Record the result rather than inheriting a machine-wide effort. Avoid `auto`, which can invoke an extra judgment model. Record the catalog context window for diagnostics; it does not itself measure live context use.

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

Magpie may route a group or fail over upstreams according to its own configuration. Preserve the requested magpie selector and report it as a route, not a promise that one physical upstream served every request. The dispatch supervisor never selects a group's members, ordering, weights, accounts, or fallback providers. An upstream change within magpie is not an omp provider violation; escaping the omp `magpie` gateway is.
