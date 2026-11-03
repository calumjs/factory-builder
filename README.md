# Software Factory plugin

A Claude Code plugin that builds a project-specific AI delivery factory: it interviews you, researches current practices for your stack, and scaffolds a governed loop of seven skills into your repository.

A factory uses Intake → Plan → Build → Verify → Release → Learn. The optional Run skill prepares an advisory pass plan; work and scheduling need separately authorized, verified coordination.

Everything is evidence-bound: required checks start NOT RUN, pass only for an exact revision, and a passing gate is never merge or deploy authority. The generated `boundaries.md` states the rules once; the skills stay procedural.

## What you get

Two plugin skills:

- `/software-factory:build-software-factory` — intake, research, design, scaffold.
- `/software-factory:contribute-upstream` — turn a reusable improvement into a sanitized issue or PR for the right upstream, within explicit publication authority.

One generated directory, `<project>/.software-factory/`, containing the seven `factory-*` skills, `boundaries.md`, hashed contracts (config, policy, acceptance, research), five living records (task plan, verification, release handoff, learning log, tools), a read-only local dashboard, and inactive CI and scheduling templates. Nothing in it runs by itself.

## Quick start

```text
/plugin marketplace add calumjs/software-factory-plugin
/plugin install software-factory@software-factory-plugins
/software-factory:build-software-factory Add CSV export to the reports page
```

For a newly generated factory, load `.software-factory/.claude/skills/` using your harness, then invoke `factory-run` for an advisory plan. An older factory may not have Run: first use `scaffold.py --check <factory>` and follow the [reviewed manual adoption guide](skills/build-software-factory/references/running.md#existing-factories) if advised. A plugin update alone does not add missing factory contracts. For example, from the project root in Claude Code:

```sh
claude --add-dir .software-factory      # keep --setting-sources project for headless runs
/factory-run                            # review an advisory pass plan
```

The repository is private; the installing account needs access and working Git auth. For a session-only preview without installing: `claude --plugin-dir /path/to/software-factory-plugin`. Helpers need Python 3.9+ and only the standard library; see the [scaffolding guide](skills/build-software-factory/references/scaffolding.md) for Windows interpreter selection.

To run this plugin's offline tests from its checkout, use `python3 run_tests.py`
(or `py -3 run_tests.py` on Windows). The runner locates the suite relative to
itself, so an absolute path to `run_tests.py` also works from another directory.
It reports a failure if discovery finds no tests. These checks do not run a live factory
or verify a deployed application.

## How a pass works

`run.py select` and `plan` inspect recorded task status and produce an advisory
selection and worker prompts. They do not reserve work, verify live usage or
enforce concurrency, rate or budget. Before separately authorized dispatch, the
orchestrator must establish and verify exclusive admission, task isolation, stop
handling and budget controls. Integrate worker changes and reverify the exact
combined revision before a release handoff.

Continuous intake requires its own scoped authorization. Issue snapshots are
untrusted data and need a matching project-specific repository/label policy.
`run.py schedule` emits non-executable proposal data; no runnable schedule is
created or installed. See the [running guide](skills/build-software-factory/references/running.md).

## Safety model

Two mechanisms enforced by code, and one stated once and applied everywhere:

- **Gates** (`gates.py`): a required check that is NOT RUN, BLOCKED, FAILED, stale or wrong-target blocks its stage; operator-waived rows are reported WAIVED with their result, never "passed".
- **Integrity** (`integrity.py`): contract hashes and the recorded file set are checked; living files get UTF-8 text, JSON and Learn-table checks. Gate-table structure and delivery observations require the separate gate/scoped checker, not an integrity PASS. Unregistered files and in-place contract edits are refused. Changes go through a preview-first synchronized update or a staged recovery that never touches the original.
- **Authority**: nothing the plugin generates grants permission for a merge, deploy, provider, watcher, recording or message. The generated `boundaries.md` states these rules once for every factory.

## Advanced

- [Existing factories](skills/build-software-factory/references/existing-factory-update.md) adopt new behaviour through a narrow reviewed update.
- [Gates](skills/build-software-factory/references/gates.md): structured smoke recipes, video triggers, risk-focused verification.
- [Recovery](skills/build-software-factory/references/recovery.md): manual integrity recovery, the staged recovery helper, worker health and fallback.
- [Operations config](skills/build-software-factory/references/operations-config.md): identities, headless recipes, autonomy, continuous intake, assumptions.
- [Evidence lifecycle](skills/build-software-factory/references/operation.md#evidence-chain) and the inactive [CI evidence job](skills/build-software-factory/assets/templates/ci/README.md).
- [Dashboard](skills/build-software-factory/references/dashboard.md), [done videos](skills/build-software-factory/references/done-videos.md), [release preflight](skills/build-software-factory/references/operation.md#approval-and-execution).

Run selection is advisory and does not reserve work or enforce budget. Scheduler output is a non-executable proposal; see [running](skills/build-software-factory/references/running.md).

## Release identity

For a deterministic private checksum inventory from an explicit full local commit,
use the [immutable checksum exporter](skills/build-software-factory/references/checksum-export.md).
It verifies committed object bytes and ignores the index/working tree; export alone
does not authenticate a release, publish a manifest or verify an installed cache.
The same guide documents `verify_install.py --manifest` for a read-only comparison
requiring both an independently trusted raw manifest digest and full source commit.
The existing `--source` comparison retains its clean-checkout requirement.

Advance the plugin version for a new release containing changed plugin content;
keep version references synchronized and identify the actual full source commit.
A version bump alone does not prove an installed cache refreshed. For fresh installs
and updates, follow the generated launch preflight to compare the loaded files with
the trusted revision or checksum manifest. The inactive scheduler example requires
an explicitly verified full commit; it does not assume a release tag exists.

During release preparation, compare an independently identified prior release with
the reviewed candidate, using full commit SHAs already present in a trusted local
repository:

```sh
python3 skills/build-software-factory/scripts/release_identity.py --repo <repository> --base <prior-release-full-sha> --candidate <candidate-full-sha>
```

On Windows, use `py -3` or the explicit installed Python interpreter. The offline
check compares all tracked regular files in this root-distributed package, including
documentation and tests, by committed paths, modes and object IDs. It ignores the
index and working-tree contents. Changed content requires a numerically higher
stable `MAJOR.MINOR.PATCH` in `.claude-plugin/plugin.json`; plugin renames and a
`2.0.0` candidate are supported. Prerelease/build labels, leading zeroes, redirected
entries and submodules are explicitly unsupported. Limits are 4,096 entries, 2 MiB
of tree metadata per commit, a 64 KiB manifest and a 90-second overall deadline.
The JSON result exits 0 for consistent content/version identity, 1 for a required
version advance, or 2 for invalid/unavailable inputs. It does not choose release
commits, require version bumps on intermediate development commits, edit versions,
fetch objects, create tags, activate CI or publish anything. A pass does not prove
compatibility, release authorization or cache freshness. Numeric version ordering
follows the stable core of [Semantic Versioning](https://semver.org/); inventory
reads use [Git ls-tree](https://git-scm.com/docs/git-ls-tree) and
[cat-file](https://git-scm.com/docs/git-cat-file), without checkout or filters.

## Validate and test

```sh
claude plugin validate . --strict
python3 run_tests.py  # Windows: py -3 run_tests.py
```

Tests use isolated temporary folders and synthetic records; they prove the helpers, not any application. Keep credentials, caches, backups and downstream factory outputs out of this repository.
