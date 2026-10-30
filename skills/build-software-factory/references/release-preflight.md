# First-release preparation for the actual project

Use this for a new deployment/provider integration, adapting it to the actual
stack, installed versions and target. CLI/packages/data/document releases use
their equivalent build/output/consumer contracts. No hosting provider is assumed.

1. Inspect the existing build scripts and platform configuration. Confirm framework
   preset, root directory, runtime/toolchain version, build command and expected
   output against the installed framework and current official provider docs. A
   generic static/public directory is not an appropriate universal output. Verify
   the prepared artifact locally when execution is authorized; record concrete
   observations and unresolved settings before the first authorized provisioning.
2. Discover currently offered integration plans/SKUs with an authorized read-only
   catalog or official provider documentation. Record observed identifiers, scope,
   region/version, included limits and costs, checked time/source and the selected
   plan. Never guess a plan ID or reuse a sample's identifier. 'Free' is not proof
   of zero future cost and grants no provisioning, billing or resource authority.
   Confirm action/target/budget scope before creating or changing resources; stop
   if the observed option differs from the accepted design.
3. Inventory required environment **names**, intended environments, management
   ownership (integration-managed versus manually managed), sensitivity, and the
   authorized validation method. Record names only where permitted, never values.
   Compare required names with actual authorized metadata after setup. Additional
   integration-managed names are not automatically errors or permission to expose
   them; inspect ownership/conflicts and least necessary access. Do not delete
   extra keys or overwrite secrets to satisfy a guessed allowlist. Environment
   names themselves may reveal private architecture: keep inventory access scoped.
4. Derive project-specific acceptance/research checks from that verified inventory.
   State required presence/ownership, relevant collisions and permitted extras
   explicitly. Generic gates validate recorded evidence; they do not enforce an
   exact environment-name allowlist, provider plan, framework preset or secret
   safety. Implement/check those assertions in the actual project when in scope.
5. After an authorized first release, identify the actual deployed/artifact subject
   revision and target. Record G3 and applicable post-action checks, including
   failure/blocked/waived states, with durable evidence. Missing logs or a running
   deployment job is not confirmation. Keep diagnosis and rollback within their
   existing scope; no step implicitly authorizes a new deployment or integration.
