# MS365 Auto Renew v2.0 checklist

## Repository and release

- [x] Source flattened to repository root
- [x] Existing local database backed up outside release tree
- [x] Runtime data, caches, environments, credentials, and secrets ignored
- [x] Version synchronized to `2.0.0`
- [x] MIT license, security policy, and contribution guide added
- [ ] Replace `OWNER`/hostname placeholders when the final GitHub repository is known

## Security

- [x] No default password or committed secret
- [x] Durable generated `secret.key` with mode `0600` where supported
- [x] One-time 15-minute setup code and 12-character password minimum
- [x] PBKDF2 hashes and stable signed sessions
- [x] Login and setup throttling
- [x] Protected APIs gated before initialization
- [x] Explicit same-origin/CORS behavior
- [x] OAuth state signed, expiring, origin-bound, and single-use
- [x] Callback clears code and uses exact `postMessage` origin
- [x] Backend-derived redirect URI
- [x] Delegated OAuth only

## WebUI

- [x] Modular API, UI, chart, and i18n files
- [x] English default plus Vietnamese and Simplified Chinese catalogs
- [x] Responsive setup, login, dashboard, accounts, logs, and settings
- [x] Loading, empty, error, toast, confirmation, disabled, and validation states
- [x] Keyboard focus, semantic controls, labels, live regions, and reduced-motion support
- [x] Intl date/number formatting, locale persistence, and dark mode
- [x] Tailwind CSS and Chart.js pinned and served locally
- [x] Development/test and scheduling-variance wording replaces evasion claims

## Packaging and automation

- [x] Multi-stage non-root Docker image with healthcheck, OCI labels, and persistent volume
- [x] Published-image and local-build Compose files
- [x] Portainer image and repository-build examples
- [x] Environment template without real secrets
- [x] Python 3.11/3.12 CI and frontend reproducibility job
- [x] Docker smoke test and dependency/secret/image scanning
- [x] GHCR multi-architecture `edge`, semantic-version, and `latest` tags
- [x] Dependabot for pip, npm, Docker, and Actions

## Documentation and QA

- [x] English README and Vietnamese README
- [x] Local Python, Docker, Portainer, proxy, update, rollback, backup, and restore instructions
- [x] Entra registration, callback, delegated permission, consent, and revocation guide
- [x] Independent-project disclaimer and no renewal guarantee
- [x] Setup/auth/OAuth/account/log/i18n/static/scheduler/Graph tests
- [ ] CI must pass in the final GitHub repository
- [ ] Replace the local dashboard capture if the public branding changes
