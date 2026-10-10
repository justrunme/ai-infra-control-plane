# Contributing

## Development setup

```bash
make venv
# activates .venv and installs requirements-dev.txt
source .venv/bin/activate
```

## Branch naming

- `feat/<short-name>`
- `fix/<short-name>`
- `chore/<short-name>`
- `docs/<short-name>`
- `ci/<short-name>`

## Commits

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`.

## Tests

```bash
make test          # unit tests
make lint
make validate      # lint + test + helm-template + policy-check + terraform-fmt
```

Optional demos: `make platform-demo`, `make e2e-kind`, `make e2e-compose`.

## Pull requests

Open against `main`. CI must be green before merge (squash).

Checklist:

- [ ] `make validate` passes locally
- [ ] Branch naming follows `feat/` / `fix/` / `chore/` / `docs/` / `ci/`
- [ ] Conventional commit messages
- [ ] Tests cover new governance / API behavior
- [ ] Manifests / Helm templates still render
