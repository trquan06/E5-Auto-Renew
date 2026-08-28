# Operations guide

## Backup

Stop the container for a consistent SQLite backup, then archive the entire persistent data directory or named volume. A valid backup contains at least `renew.db` and `secret.key`; SQLite `-wal`/`-shm` files may exist while the service is running.

```bash
docker compose stop webui
tar -czf ms365-data-$(date +%Y%m%d).tgz data/
docker compose start webui
```

Store backups encrypted with restricted access. Test restoration on an isolated host. Never publish a backup or attach it to an issue.

## Restore

1. Stop the service.
2. Move the current data directory aside so rollback remains possible.
3. Restore the complete archived data directory, preserving ownership for UID/GID `10001`.
4. Start the exact application version used to create the backup, verify login and account decryption, then upgrade if desired.

Restoring a database without its matching `secret.key` makes encrypted Microsoft tokens unreadable. Supplying a different `SECRET_KEY` has the same effect.

## Update

1. Read release notes and security advisories.
2. Back up the data volume.
3. Pull an immutable release tag: `docker compose pull`.
4. Recreate: `docker compose up -d`.
5. Verify `/health`, container health, login, account list, scheduler state, and one authorized connection test.
6. Keep the previous image until the observation window is complete.

## Rollback

Set `image:` to the previous immutable tag and recreate the container. If the new version changed data incompatibly, stop the service and restore the matching pre-update data backup before starting the older image. Never run two instances against the same SQLite volume.

## Logs and retention

Application logs go to stdout/stderr for the container platform to collect. Execution logs live in SQLite and can be filtered or cleared from the WebUI. Avoid debug logging in production. Configure Docker/platform log rotation independently so setup codes and operational metadata are not retained indefinitely.

## Incident response

If exposure is suspected, stop external access, preserve sanitized diagnostic evidence, revoke Entra consent and client secrets, rotate the administrator password, generate a new application key only after reconnecting accounts, and review reverse-proxy/access logs. Report product vulnerabilities using `SECURITY.md`.
