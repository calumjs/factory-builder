# Evidence subjects across squash, rebase and merge

Use this recipe when the reviewed head, integrated commit and evidence-storage
commit differ. It supplements [operation.md](operation.md) and [gates.md](gates.md);
it does not introduce cross-revision gate acceptance or a new release policy.

| Identity | Meaning | How it is established |
|---|---|---|
| H: reviewed head | Exact subject used by the pre-merge observations | Actual checkout/artifact and retained test/review evidence |
| M: integrated commit | Actual result of squash, rebase, merge or fast-forward | Independently verified repository/PR result, not a guessed branch tip |
| D: delivered subject | Exact commit/artifact actually deployed or published | Actual delivery observation, including target and artifact identity |
| E: evidence storage | Commit storing the observations and handoff | Exact reviewed storage commit after it exists; never substituted for H/M/D |

Record full immutable identities, their source and the reason for each selected
assessment subject in the external task/release handoff. H, M and D may coincide,
but do not assume they do. Branch names, short hashes, issue labels and a current
HEAD are insufficient evidence of the intended subject. Do not resolve them
automatically or derive the requested subject from whichever row happens to pass.

## 1. Compare the explicit local commit trees

After separately establishing H and M, inspect their whole committed root-tree
identities in an approved local repository. A squash/rebase may produce a different
commit with the same tree; a merge may include other changes or conflict resolutions.
Even two commits with the same tree remain distinct subjects: parents, metadata,
build inputs outside Git, execution environment and actual delivery can differ.
Git documents the commit/tree distinction in [git-commit-tree](https://git-scm.com/docs/git-commit-tree)
and tree dereferencing in [revisions](https://git-scm.com/docs/revisions).

This read-only Python example runs with the trusted builder's `scripts` directory
on its import path. Supply an explicit approved repository path and independently
verified **full** SHA-1 or SHA-256 commit IDs. It reuses the existing bounded local
Git reader: replace objects are disabled, all fetch transports are denied, no
credentials are requested or application code executed, and each output is capped at
128 bytes with the reader's 30-second timeout. There is no checkout, ref lookup,
network fetch, recursive tree walk, worktree comparison or readiness verdict.

```python
import os
from pathlib import Path

from ci_evidence import Git, full_sha
from integrity import safe_path


def compare_subject_trees(repo, reviewed, integrated):
    reviewed, integrated = full_sha(reviewed), full_sha(integrated)
    redirects = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")
    if any(name in os.environ for name in redirects):
        raise ValueError("Use an environment without repository/object-store redirects")
    git = Git(safe_path(Path(os.path.abspath(repo))))

    def tree(commit):
        if git.read("cat-file", "-t", commit, limit=128).strip() != b"commit":
            raise ValueError("An explicit local commit object is required")
        value = git.read("rev-parse", "--verify", commit + "^{tree}", limit=128)
        identity = full_sha(value.decode("ascii").strip())
        if git.read("cat-file", "-t", identity, limit=128).strip() != b"tree":
            raise ValueError("The local root tree is unavailable")
        return identity

    head_tree, merged_tree = tree(reviewed), tree(integrated)
    return {"reviewed_subject": reviewed, "integrated_subject": integrated,
            "reviewed_tree": head_tree, "integrated_tree": merged_tree,
            "trees_equal": head_tree == merged_tree,
            "evidence_transferred": False}
```

Missing objects, wrong object types or malformed identities stop the comparison;
do not retry with a short prefix or fetch implicitly. Obtain missing objects only
through a separately authorized acquisition step, then repeat against the same
verified identities. Equal root trees identify the same committed hierarchy; this
does not inspect every blob or establish local availability of submodules, LFS
payloads, dependencies or other execution inputs. A dirty worktree cannot change
this identity comparison, but it can invalidate a claimed test checkout.

Record both commit IDs, both tree IDs, comparison result, tool/repository identity
and observation time. If trees differ, preserve that result and inspect the actual
delta through the normal review process. Even a difference consisting only of
evidence files is not full-tree equality; use the separate evidence-storage rules
below rather than deleting paths from the comparison until it becomes equal.

## 2. Keep observations on the subject actually checked

Keep existing H observations, including FAILED/BLOCKED/NOT RUN results and optional
waivers, under H. A tree comparison is supporting context for a review; it is not a
test run, review approval or permission to change their Revision cells to M.

To assess those original pre-merge observations, pass H explicitly to the trusted
checker against the intended, integrity-valid record copy:

```text
python scripts/gates.py --factory <record-copy> --stage pre-merge --revision <full-H>
```

This says whether the recorded requirements for H are satisfied. It says nothing
about required checks for M. If the release process requires readiness for M,
inspect and execute the still-required checks against the exact M checkout/artifact
under the existing authority and budget, then record their actual new observations
for M. Equal trees do not waive this obligation under the current exact-subject
checker. Use the existing [gate-record preview/apply flow](incremental-workflow.md)
to retain the prior row as history; keep durable original logs and reviews too.
Missing execution authority or inputs means BLOCKED/NOT RUN, never copied PASS.
Explicit optional rows remain WAIVED with their observations; do not reset them
merely to make the subject change look successful.

The optional `--reviewed-revision` extension suggested in issue #41 is **not
implemented**. There is no implicit tree-equality exception in `gates.py` or
`ci_evidence.py`. A squash commit need not descend from H: do not force it through
the CI adapter's evidence-only ancestry policy. Use a subject/storage pair that
actually satisfies the documented policy, or leave that assessment blocked for
an explicit policy decision. This recipe changes no CI wiring or gate semantics.

## 3. Select the delivered subject after evidence-only commits

Release establishes D from the actual authorized delivery, not from M, H or HEAD
by assumption. Record and assess required G3 and other post-action observations
for D and the observed target:

```text
python scripts/gates.py --factory <record-copy> --stage post-merge --revision <full-D> --target <actual-target>
```

If E later stores those observations, continue assessing D; do not rename D to E
because the repository now points at E. Inspect E's complete diff against its
intended subject and the agreed evidence envelope; source, configuration, policy,
test or dependency changes are not automatically evidence-only. For the optional
CI adapter use its explicit `--subject`/`--storage` arguments and documented clean
checkout, ancestry and path checks in [ci/README.md](../assets/templates/ci/README.md).
If E itself triggers another deployment, independently establish the new actual
subject/target and obtain the required new post-action observations. Same source
content does not establish that a new deployment ran or behaved correctly.

The `--factory` path selects current record files; `--revision` does not check out
a commit. Preserve the provenance of the chosen record-storage copy and any
reviewed evidence overlay. Do not replace failed history or choose an older
passing subject to describe a newer failed delivery.

## Operator and dashboard handoff

State: “Pre-merge assessment subject H because these checks ran on H; integrated
subject M; actual delivery subject D at target T; records stored at E.” Include
the exact identities and links to observed evidence, not these literal placeholders.
Report each stage separately when its subjects differ. The current dashboard shows
each row's recorded revision and warns that single-subject readiness comes from the
gate checker; it has no subject-selection-and-reason control. This recipe supplies
the handoff explanation, not that requested dashboard feature. Do not interpret
counts across recorded subjects as a PASS for HEAD or the delivered subject.
