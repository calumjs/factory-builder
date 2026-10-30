# Scaffold mechanics

Requires Python 3.9+ and its standard library. No dependencies, network calls or paid services are performed by the helpers. The package may live anywhere readable.

## Interpreter and preview

Choose a working interpreter before running a helper. On Windows, `python` can be a Store alias. The bundled `scripts/run-python.ps1` checks PATH candidates (`python`, `python3`, `py -3`) and per-user Python installations, skips Store aliases, verifies Python 3.9+, prints the executable used and forwards arguments. It installs nothing. Alternatively use an explicitly verified interpreter path. On other systems, verify `python3 --version` or the selected environment.

From the skill directory, after the user authorizes local scaffolding:

```sh
python scripts/scaffold.py --config config.json --research research.json --target /approved/project
# Review preview, then apply within the existing local authorization:
python scripts/scaffold.py --config config.json --research research.json --target /approved/project --apply
python scripts/scaffold.py --check /approved/project/.software-factory
```

Windows equivalent: `& ./scripts/run-python.ps1 ./scripts/scaffold.py --config config.json --research research.json --target C:/approved/project`. Paths in these examples are placeholders for the user's authorized target.

Populate `assets/example-config.json` from intake. Read [operations-config.md](operations-config.md) only when identities, automation, headless tools or specialized review need configuration. Research uses `assets/example-research.json` and [research.md](research.md). Omitted research produces an explicitly blocked draft. The helper never researches the web or verifies source truth.

The target must already exist. Symlinks/junctions are refused. Existing `.software-factory` output is refused even when empty; there is no force switch. For an existing factory, propose a narrow reviewed change rather than deleting it. Only the new output directory is created; repository instructions, settings, CI and application files are preserved.

## Contracts and living records

Schema 2 `manifest.json` hashes contract artifacts: phase skills, policy, acceptance criteria, config, research decisions, provenance and operating fragments. Text hashes canonicalize UTF-8 BOM and CRLF/CR to LF; `.gitattributes` also requests LF inside the new factory folder. A changed contract blocks integrity until a reviewed migration or new baseline is deliberately accepted. Never silently rebaseline it.

Five living artifacts are listed but not hashed: `verification.md`, `task-plan.json`, `learning-log.md`, `release-handoff.md` and `tools.json`. These are expected to evolve. The checker validates file presence and basic text/JSON structure, not evidence truth or authorization. Review meaningful changes to permissions, enablement, tools and release decisions. Unexpected files, missing files and malformed living JSON are still errors.

The dedicated `dashboard/` bundle and initial HTML are contracts. Open its initial snapshot directly; refresh using the bundled helper to an HTML/JSON file **outside** the factory. It creates no caches in the factory. See [dashboard.md](dashboard.md) for source/freshness semantics, project-specific profiles, safe existing-UI integration and narrow existing-factory adoption. Keep runtime snapshots and adapter inputs private and outside the manifest directory.

## Delivery gates

verification.md includes required G1/G2/G3, A1... acceptance checks, R1... selected research checks, and post-G3 V1 when narrated done videos are enabled. Records start NOT RUN, except an explicitly accepted no-release G3 exclusion may be NOT APPLICABLE. Read the generated recording rules; replace designs with actual inspected commands/manual procedures and observations.

```sh
python scripts/gates.py --factory /approved/project/.software-factory --stage pre-merge --revision actual-reviewed-revision
# Only after a separately authorized action; the target may be a URL or artifact identity:
python scripts/gates.py --factory /approved/project/.software-factory --stage post-merge --revision actual-merged-revision --target actual-target
```

The gate helper first checks contract integrity and synchronized config/policy. It then validates stage, mandatory rows, actual revision/target, environment, timestamp, successful exit/manual observation and evidence for all required checks. A nonzero exit blocks readiness/confirmation. Pre-action readiness does not require future post-action observations. Gate validity is not evidence truth or release authority; no application command executes.

For a write-free proposed table, use `python scripts/gates.py --factory /approved/project/.software-factory --plan`. Do not append duplicate active rows. For an existing factory, use the [narrow reviewed update](existing-factory-update.md); no force/rescaffold operation is available. Legacy schema 1 requires a separate migration.

## Record status and evidence

New factories also contain ci/README.md and ci/job.example.py: an inactive portable
CI adoption template, not a root workflow. It invokes a trusted pinned installed
builder helper to assess explicit tested-subject versus evidence-storage commits.
See [evidence-lifecycle.md](evidence-lifecycle.md); CI activation/required-check setup
needs separate scope. Do not execute a PR-supplied helper in a privileged job.

`task-plan.json` is the authoritative atomic task/evidence record. Use the status helper rather than separately editing a JSON status and a Markdown evidence table:

```sh
python scripts/status.py --factory /approved/project/.software-factory --task T1 --status done --result passed --check "acceptance A1" --evidence "Observed check output; evidence artifact reference" --revision actual-revision --environment actual-environment
# The same command with --apply records the reviewed event within authorized local writes.
```

The preview writes nothing. `--apply` updates status and appends an evidence event together, recording timestamp, revision, environment, result and prior status. A `done` task requires a passing result and completed dependencies. Failed/blocked/not-run evidence must stay distinct. The helper records supplied evidence; it runs no check and grants no release authority. A lock prevents simultaneous recordings; after an interrupted operation, inspect any remaining lock/temp file before recovery. Keep secrets out of evidence text.

## Claude Code integration

Generated skills live at `.software-factory/.claude/skills/factory-<name>/` and resolve their artifact root three levels up. Start Claude from the project root with `claude --add-dir .software-factory` (for scoped or headless use add `--setting-sources project`; an empty source list can hide generated skills even though the plugin loads) and invoke `/factory-run` or any phase directly. See [added-directory loading](https://code.claude.com/docs/en/skills#load-skills-from-a-directory-outside-the-project) and the [CLI reference](https://code.claude.com/docs/en/cli-reference) (read 2026-10-30).

Before commands are assigned, run the generated [launch preflight](../assets/templates/launch-guide.md): record the loaded plugin version and source, confirm required helper availability, let the human owner resolve any workspace-trust prompt, confirm the six phase skills and any separately adopted Run skill are discovered with an actual scoped Skill call, and check the exact resolved interpreter plus helper argv against the task's execution permissions — a wrapper can pick a binary an allowlist does not cover. Newly scaffolded factories include Run; an older six-skill factory does not acquire it from a plugin upgrade. Missing required tooling is blocked, not a passing gate. Report a blocked command and keep its checks pending; use the normal bounded approval process rather than another launch route or broader permissions. Updating the plugin does not migrate existing factory contracts; use the narrow reviewed update.

No hooks, tool preapproval, MCP server or settings changes are bundled. `gitignore.fragment` is an optional root ignore fragment to review and merge by hand; it adds Next.js/TypeScript/Vercel/Playwright patterns only when the configured stack, target or test commands name them (current Next.js docs say `next-env.d.ts` is regenerated and should be ignored — see [Next.js TypeScript](https://nextjs.org/docs/app/api-reference/config/typescript#next-envdts), read 2026-10-30). Confirm the actually installed tooling before adopting inferred patterns. The helper never edits root ignore rules, deletes or untracks files. Dashboard snapshots use `factory-overview.html/json` by convention, outside the factory.

`upstream-provenance.json` deliberately leaves the repository URL null: resolve the component's source from installed plugin metadata, then use the contribution skill; never copy a private repository identity into shared output.

## Offline tests

`python -m unittest discover -s scripts -p "test_*.py" -v` exercises helpers in temporary directories, including preservation, integrity, line endings, living records, evidence updates, default delivery gates (NOT RUN blocks) and synthetic research mapping. It does not validate an application or prove online research occurred.

Official format/discovery references: https://code.claude.com/docs/en/skills and https://code.claude.com/docs/en/plugins/create (checked 2026-10-29).
