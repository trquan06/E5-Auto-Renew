# MS365 Auto Renew v2.0 release plan

## Objective

Publish a clean, source-available v2.0.0 repository with safe first-run behavior, delegated OAuth, a local multilingual SPA, reproducible containers, automated security checks, and complete operator documentation.

## Completed implementation

1. Flatten the application to the repository root and move local database/legacy source outside the release tree.
2. Remove default credentials and example secrets; persist a generated encryption/signing key with restrictive permissions.
3. Add one-time setup, password hashing, stable JWT sessions, request throttling, pre-setup route gating, constrained CORS, signed expiring OAuth state, exact-origin callback messaging, and delegated-only accounts.
4. Replace the legacy page with modular API/i18n/UI/chart JavaScript, responsive views, English/Vietnamese/Simplified Chinese catalogs, dark mode, and local pinned assets.
5. Add a non-root multi-stage Dockerfile, image/build Compose files, Portainer examples, health checks, OCI labels, GitHub CI/release workflows, security scans, and Dependabot.
6. Rewrite English/Vietnamese READMEs plus deployment, Entra, operations, security, and contribution guides with clear limitations and no renewal guarantee.
7. Expand automated tests for setup, authentication, OAuth state/origin, persistence, delegated CRUD, log retention, translations, static assets, scheduler, and Graph execution.

## Release gates

- `npm ci && npm run build` produces no uncommitted frontend asset changes.
- `pytest -q` passes on Python 3.11 and 3.12.
- Docker image builds, starts as UID 10001, reaches healthy state, and serves the setup flow.
- Secret/dependency/image scanners report no unresolved high-severity release blockers.
- No database, secret key, environment file, token, credential, cache, or local log is tracked.
- Documentation placeholders such as `OWNER` are replaced before public publishing.
