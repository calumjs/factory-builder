# Launch preflight

Do this once per session before assigning helper commands, in whatever harness is running the factory. It records what is loaded and confirms the tooling; it changes nothing.

## 1. Pin the builder

Record the builder plugin's name, version and the directory it was loaded from (for a Git checkout, the full commit and whether the tree is dirty; for an archive, its trusted revision or checksum). A version string alone does not identify code. Resolve `<trusted-skill-root>` to `skills/build-software-factory` inside that directory and confirm `scripts/scaffold.py`, `scripts/status.py`, `scripts/gates.py` and `scripts/run.py` are present. A missing helper is a BLOCKED tooling preflight, not a passing gate; do not substitute a copied or improvised script, and manual observations recorded meanwhile do not satisfy a still-required automated check. Do not read credentials while pinning, and do not assume the application's Git origin is the plugin source. Updating the plugin is a separate authorized action, and it does not migrate this factory's contracts — use the builder's reviewed update for that.

For a fresh install or update, verify the content actually loaded: resolve the real
installed plugin directory, then compare its complete relevant file inventory and
per-file SHA-256 bytes with a trusted, independently identified release checkout or
published checksum manifest. Record the full source commit SHA, actual loaded path,
comparison result and any extra, missing or changed files in approved evidence.
A version label, a Git HEAD with unreviewed local changes, or the checksum of an
archive alone does not prove the extracted cache matches that commit. If the source
or comparison is unavailable or differs, record the revision as unverified and stop
claims that a particular update was loaded. Do not assume updating refreshed a cache.
`upstream-provenance.json` initially leaves `source_revision` null; updating the
hashed provenance contract requires a reviewed, selective migration.

## 2. Load the skills

Load the seven skills in `.software-factory/.claude/skills/` using your harness's mechanism for an additional skills directory, keeping the project's own settings and instructions in effect. Confirm all seven are discovered by invoking one scoped skill, not by reading its text. If discovery is blocked, report the version, path and policy and stop; do not copy the skills elsewhere, change settings or bypass a policy to make it work.

## 3. Trust and permissions

If your harness asks for a workspace-trust decision for this checkout, the human owner makes it in the normal UI after inspecting the path, settings and integrations. Keep the affected task BLOCKED until then; pause any active pickup through its authorized control. A non-interactive session may show no prompt — that absence does not prove the owner accepted trust. Trust grants no tool permission, integration approval or task authority, and a denied action remains denied after it.

Before verification or release, record the interpreter's absolute path and the exact helper argv, target and subject you intend to run, and check them against the task's execution permissions. If a permission rule blocks a helper, report the exact command and keep its checks NOT RUN or BLOCKED; obtain bounded task-specific authority through the normal process rather than another interpreter, wrapper or launch mode. Example argv to review:

```json
["<existing-interpreter>","<trusted-skill-root>/scripts/gates.py","--factory","<factory-root>","--stage","pre-merge","--revision","<actual-subject>"]
```

## 4. Headless runs

For any separately authorized unattended pass, independently verify the intended harness command, authentication, output, restrictions and data boundary. `run.py schedule` produces only a non-executable proposal; it never selects a tools.json command or installs a scheduler. An explicitly supplied argv recipe can be shown as inert review data. Before dispatch or scheduling, establish and test exclusive admission, stop handling and budget enforcement.
