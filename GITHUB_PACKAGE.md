# GitHub package

This repository package contains the source code and deployment files for
Microsoft 365 Auto Renew.

Before publishing:

1. Review `.env.example` and keep real credentials only in a local `.env` file.
2. Do not commit runtime files from `data/` except `data/.gitkeep`.
3. Create a new GitHub repository, extract this package, then commit and push
   the extracted `ms365-auto-renew` directory.

The generated ZIP intentionally excludes virtual environments, installed
Node.js dependencies, caches, local databases, encryption keys, logs, and
other ignored build/runtime output.
