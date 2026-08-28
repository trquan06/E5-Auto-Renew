# GitHub package

This repository package contains the source code and deployment files for
Microsoft 365 Auto Renew.

Before publishing:

1. Review `.env.example` and keep real credentials only in a local `.env` file.
2. Do not commit runtime files from `data/` except `data/.gitkeep`.
3. Create a new GitHub repository, extract this package, then commit and push
   the extracted `E5-Auto-Renew` directory.

No filtered ZIP-generation process is claimed. Before distributing an archive,
inspect its contents separately and confirm that virtual environments,
`node_modules`, caches, `.env`, local databases, encryption keys, logs, backups,
and other runtime output are absent.
