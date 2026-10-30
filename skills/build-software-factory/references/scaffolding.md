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

## Delivery gates

`verification.md` starts with required G1 (pre-merge local smoke on a production build), G2 (change-targeted tests) and G3 (post-merge smoke on the deployed URL) rows, all NOT RUN. Record actual results in those rows, then check them:

```sh
python scripts/gates.py --factory /approved/project/.software-factory --stage pre-merge --revision actual-revision
python scripts/gates.py --factory /approved/project/.software-factory --stage post-merge --revision merged-revision
```

Exit 0 only when every required gate for the stage is PASSED with evidence for that exact revision; NOT RUN, BLOCKED, FAILED, a stale revision or a removed gate exits 1. The helper reads records only; it executes no tests and grants no merge or deploy authority.

Schema 1 factories need a separately reviewed migration; this helper does not rewrite their manifests. Intentional content changes are distinct from newline-only changes.

## Record status and evidence

`task-plan.json` is the authoritative atomic task/evidence record. Use the status helper rather than separately editing a JSON status and a Markdown evidence table:

```sh
python scripts/status.py --factory /approved/project/.software-factory --task T1 --status done --result passed --check "acceptance A1" --evidence "Observed check output; evidence artifact reference" --revision actual-revision --environment actual-environment
# The same command with --apply records the reviewed event within authorized local writes.
```

The preview writes nothing. `--apply` updates status and appends an evidence event together, recording timestamp, revision, environment, result and prior status. A `done` task requires a passing result and completed dependencies. Failed/blocked/not-run evidence must stay distinct. The helper records supplied evidence; it runs no check and grants no release authority. A lock prevents simultaneous recordings; after an interrupted operation, inspect any remaining lock/temp file before recovery. Keep secrets out of evidence text.

## Claude Code integration

The plugin builder is `/software-factory:build-software-factory`. Generated six-phase folders live at `.software-factory/.claude/skills/factory-<phase>/`. Start Claude from the project root with `claude --add-dir .software-factory`, then invoke `/factory-intake`, `/factory-plan`, `/factory-build`, `/factory-verify`, `/factory-release` or `/factory-learn`. Confirm discovery under the installed Claude version and organization policy. The phase instructions resolve their artifact root three levels above their containing folder.

No hooks, tool preapproval, MCP server or settings changes are bundled. `gitignore.fragment` is an optional root ignore fragment to review and merge manually; the helper never edits root ignore rules. Keep non-secret `.env.example` files if useful. Stage explicit reviewed paths; avoid blanket staging of caches, backups, credentials or factory outputs.

The generated `upstream-provenance.json` deliberately leaves the repository URL unverified/null. Resolve the reusable component's source from installed plugin metadata, then use the bundled contribution skill; never copy a private repository identity into shared output or infer posting authority from provenance.

## Offline tests

`python -m unittest discover -s scripts -p "test_*.py" -v` exercises helpers in temporary directories, including preservation, integrity, line endings, living records, evidence updates, default delivery gates (NOT RUN blocks) and synthetic research mapping. It does not validate an application or prove online research occurred.

Official format/discovery references: https://code.claude.com/docs/en/skills and https://code.claude.com/docs/en/plugins/create (checked 2026-10-29).
