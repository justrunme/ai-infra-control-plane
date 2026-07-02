# Repository Working Agreements

## Language

- Write code comments, documentation, commit messages, branch names, PR titles, and PR descriptions in English.
- Keep implementation comments short and only add them when they clarify non-obvious behavior.

## Branches

- Do not use personal, tool, or agent prefixes such as `codex/`.
- Use thematic branch names based on the change type and scope:
  - `feat/<topic>` for new capabilities.
  - `fix/<topic>` for bug fixes.
  - `ci/<topic>` for CI and workflow changes.
  - `docs/<topic>` for documentation-only changes.
  - `chore/<topic>` for maintenance.
- Keep branch names short, lowercase, and hyphenated.

## Commits And Pull Requests

- Use concise Conventional Commit-style messages, for example `feat: add Ollama backend probe`.
- Keep PRs focused and reviewable; one engineering task per PR.
- Open draft PRs by default until CI is green.
- PR descriptions should include what changed, why it changed, and how it was validated.
- For a consistent `main` history on GitHub, prefer **Squash and merge** from the `justrunme` account. Local commits should use the same `user.name` / `user.email` as the GitHub identity that owns the repository (or the GitHub noreply address) so squash metadata does not alternate between personal and org identities.

## Validation

- Run the narrowest meaningful checks for touched files.
- For API changes, run `make test` and `make lint`.
- For Helm chart changes, run `helm template ai-control-plane infra/helm/ai-control-plane`.
- For Terraform changes, run `terraform -chdir=infra/terraform/hetzner-vm fmt -check`.

