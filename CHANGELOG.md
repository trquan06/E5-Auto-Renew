# Changelog

## 2.0.0 - 2026-08-28

### Added

- Secure first-run setup, password authentication, rate limiting, and pre-setup API gating.
- Delegated Microsoft Graph OAuth with signed, expiring, single-use state and encrypted token persistence.
- English, Vietnamese, and Simplified Chinese WebUI with local pinned frontend assets.
- Non-root Docker image, named-volume Compose deployments, Portainer examples, and health checks.
- Python 3.11/3.12 and frontend CI, Docker smoke/publish workflow, security scans, and Dependabot configuration.

### Security

- Forwarded headers are trusted only from explicit proxy IP addresses or CIDR ranges; wildcard trust is rejected.
- Browser responses include CSP, clickjacking, MIME-sniffing, referrer, permissions, and sensitive-API cache protections.
- Runtime environment files, databases, keys, logs, backups, Git metadata, and caches are excluded from Git and Docker build context.

### Operational notes

- Version 2.0.0 does not guarantee Microsoft 365 Developer subscription renewal or eligibility.
- Back up `renew.db` and its matching `secret.key` together before upgrading.
- Production deployments should pin `ghcr.io/trquan06/e5-auto-renew:2.0.0` or, preferably, the published digest.
