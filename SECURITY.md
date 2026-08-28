# Security policy

## Supported versions

Security fixes are provided for the latest 2.x release. Version 1.x has insecure deployment defaults and should be upgraded before network exposure.

## Reporting a vulnerability

Do not open a public issue containing credentials, tokens, authorization codes, database contents, or exploit details. Use the repository's private security advisory feature. Include the affected version, deployment shape, reproduction steps, impact, and a minimal sanitized proof of concept. Maintainers should acknowledge a complete report within seven days.

## Deployment baseline

- Complete the first-run wizard immediately and use a unique password of at least 12 characters.
- Use HTTPS for every non-local deployment and set `PUBLIC_BASE_URL` to the exact external origin.
- Do not use wildcard CORS origins or expose port 8080 directly to the public internet.
- Restrict the persistent data directory to the container user and trusted backup operators.
- Keep `renew.db` and `secret.key` together. Rotate the key only after reconnecting every Microsoft account.
- Use the least delegated Graph permissions that support the enabled workloads, review consent periodically, and revoke access when the service is retired.
- Pin immutable image versions for production and review CI scan findings before an update.

## Secret handling

The application generates `data/secret.key` with mode `0600` when `SECRET_KEY` is absent. It encrypts Microsoft tokens at rest and signs local JWT/OAuth state. Logs and API responses must never contain decrypted tokens, passwords, setup code digests, or client secrets. The setup code itself appears only in server logs while setup is incomplete and expires after 15 minutes.
