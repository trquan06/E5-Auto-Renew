# Deployment guide

## Local Python

Install Python 3.11 or 3.12 and Node.js 20. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
npm ci
npm run build
python run.py
```

On Windows PowerShell activate with `.venv\Scripts\Activate.ps1`. Open `http://localhost:8080`, then copy the one-time setup code from the terminal. Runtime files are created in `data/` and are intentionally ignored by Git.

## Docker Compose: build locally

```bash
cp .env.example .env
docker compose -f compose.build.yml up -d --build
docker compose -f compose.build.yml logs --follow webui
```

The image runs as UID/GID `10001`. On Linux, prepare a bind mount with `mkdir -p data && sudo chown 10001:10001 data`. Do not make the directory world-writable.

## Docker Compose: published image

Replace the `OWNER` placeholder in `compose.yml` with the GitHub organization/user that published the image. Prefer an immutable release tag in production:

```yaml
image: ghcr.io/example/ms365-auto-renew:2.0.0
```

Then run `docker compose up -d` and inspect `docker compose logs webui` for the first-run code. The image supports `linux/amd64` and `linux/arm64` when published by the included release workflow.

## Portainer

Two examples live in `portainer/`:

- `stack.image.yml` pulls a GHCR image.
- `stack.build.yml` builds from a Git repository.

Paste the selected file into a new Stack, replace all `OWNER`, repository, hostname, and `PUBLIC_BASE_URL` placeholders, and deploy. Both examples use a named volume. Find the one-time code in the container logs. Back up the named volume from the Docker host before every update.

## HTTPS reverse proxy

Remote OAuth requires HTTPS. Configure the proxy to pass the original host and protocol, then set:

```dotenv
PUBLIC_BASE_URL=https://ms365.example.com
```

Example Nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
}
```

Expose only ports 80/443 at the edge, redirect HTTP to HTTPS, and restrict direct access to port 8080. The Entra redirect URI must be `${PUBLIC_BASE_URL}/api/accounts/oauth/callback` exactly.

## Verification

```bash
curl --fail https://ms365.example.com/health
docker inspect --format '{{.State.Health.Status}}' ms365-auto-renew
```

Before setup, protected APIs return `503 setup_required`. After setup, they return `401` without a valid bearer token. This is expected.
