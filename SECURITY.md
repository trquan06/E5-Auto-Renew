# Security policy

## Supported versions

This source tree is preparing version 2.0.0; it does not claim that a public release has passed its release gates. After publication, only versions explicitly listed in GitHub Releases as supported receive security fixes. Version 1.x has insecure deployment defaults and should not be exposed to a network.

## Reporting a vulnerability

Do not open a public issue containing credentials, tokens, authorization codes, database contents, or exploit details. Use the repository's private security advisory feature. Include the affected version, deployment shape, reproduction steps, impact, and a minimal sanitized proof of concept. Maintainers should acknowledge a complete report within seven days.

## Deployment baseline

- Complete the first-run wizard immediately and use a unique password of at least 12 characters.
- Use HTTPS for every non-local deployment and set `PUBLIC_BASE_URL` to the exact external origin.
- Do not use wildcard CORS origins or expose port 8080 directly to the public internet.
- Set `FORWARDED_ALLOW_IPS` to only the reverse proxy IP/CIDR. Wildcard forwarded-header trust is rejected.
- Restrict the persistent data directory to the container user and trusted backup operators.
- Keep `renew.db` and `secret.key` together. Rotate the key only after reconnecting every Microsoft account.
- Use the least delegated Graph permissions that support the enabled workloads, review consent periodically, and revoke access when the service is retired.
- Pin immutable image versions for production and review CI scan findings before an update.

## Secret handling

Never commit or publish `.env`, `renew.db`, `secret.key`, SQLite sidecars, access/refresh tokens, tenant client secrets, administrator passwords, notification tokens/webhooks, logs, or backups. The application generates `data/secret.key` with mode `0600` when `SECRET_KEY` is absent. It encrypts Microsoft tokens at rest and signs local JWT/OAuth state. The database and its matching key must be backed up together, and both are sensitive.

Logs and API responses must never contain decrypted tokens, passwords, setup code digests, or client secrets. The setup code itself appears only in server logs while setup is incomplete and expires after 15 minutes.

If a credential enters Git or a public artifact, revoke or rotate it first: remove Entra client secrets/consent and active sessions, rotate notification tokens/webhooks and administrator credentials, then reconnect affected accounts. Removing a file in a later commit is not sufficient. Purge Git history when necessary, coordinate any force-push with collaborators, and scan the remote history again afterward.

## Automated scan policy

The security workflow fails on any `pip-audit` finding, any Gitleaks detection in the fetched full history, or a Trivy filesystem vulnerability/misconfiguration/secret finding rated High or Critical when a fix is available. Findings must be fixed or explicitly reviewed and documented before release; workflow failures are not skipped to publish.
