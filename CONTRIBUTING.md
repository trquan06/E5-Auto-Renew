# Contributing

Thanks for improving MS365 Auto Renew. Keep changes focused on authorized development/test workflows and avoid claims that the software guarantees subscription renewal or bypasses provider policy.

## Development workflow

1. Create a topic branch from the current default branch.
2. Install Python 3.11 or 3.12 dependencies from `requirements-dev.txt` and frontend dependencies with `npm ci`.
3. Make backend messages in English and put every user-facing SPA string in all three i18n catalogs.
4. Run `npm run build` after changing HTML, JavaScript, Tailwind inputs, or pinned frontend dependencies.
5. Run `pytest -q`, then build the Docker image and verify `/health`.
6. Never commit `.env`, databases, secret keys, token values, logs, or real tenant/application identifiers.

Pull requests should describe the user-visible change, security impact, test evidence, documentation updates, and any data migration. Add tests for setup lifecycle, authentication, OAuth state/origin validation, encrypted persistence, scheduling, and log retention when those areas change.

Use conventional, imperative commit subjects where practical. Report security defects through the private process in `SECURITY.md`.
