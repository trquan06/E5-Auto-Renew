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
git clone https://github.com/trquan06/E5-Auto-Renew.git
cd E5-Auto-Renew
cp .env.example .env
docker compose -f compose.build.yml up -d --build
docker compose -f compose.build.yml logs --follow webui
curl --fail http://localhost:8080/health
```

In PowerShell use `Copy-Item .env.example .env`. The default `e5_data` named volume is writable by the image's UID/GID `10001` and persists through container recreation. For an intentional Linux bind-mount override, use `mkdir -p data && sudo chown 10001:10001 data`; do not make it world-writable.

## Docker Compose: published image

`compose.yml` uses the immutable production image tag:

```yaml
image: ghcr.io/trquan06/e5-auto-renew:2.0.0
```

Run `docker compose up -d` and inspect `docker compose logs webui` for the first-run code. Tagged releases publish `linux/amd64` and `linux/arm64` through `.github/workflows/docker.yml`; verify the workflow and pull by digest before production rollout.

The `main` branch publishes `edge`. A `vX.Y.Z` tag publishes `X.Y.Z`, `X.Y`, `X`, and `latest`. Production deployments should use the full semantic version or the manifest digest, not `edge` or `latest`.

## Portainer

Two examples live in `portainer/`:

- `stack.image.yml` pulls a GHCR image.
- `stack.build.yml` builds from a Git repository.

Paste the selected file into a new Stack, set `PUBLIC_BASE_URL` and the proxy/network settings for the deployment, and deploy. Both examples use the real repository/image and a named volume. Find the one-time code in the container logs. Back up the named volume from the Docker host before every update.

## HTTPS reverse proxy

Remote OAuth requires HTTPS. Configure the proxy to pass the original host and protocol, then set:

```dotenv
PUBLIC_BASE_URL=https://ms365.example.com
FORWARDED_ALLOW_IPS=127.0.0.1
```

Set `FORWARDED_ALLOW_IPS` to the exact source IP address or CIDR of the reverse proxy as seen by the application. The safe `127.0.0.1` default deliberately trusts no typical Docker bridge peer; a host proxy may appear as the Docker bridge gateway rather than loopback, so determine and allow only that deployment-specific address. Wildcard trust is rejected. If the proxy is another container, attach both services to a private Docker network, use only that proxy address/network, and do not publish the application port publicly.

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

Enable HSTS at the HTTPS edge only after the hostname is permanently HTTPS-ready; the application intentionally does not emit HSTS for direct localhost HTTP.

## Verification

```bash
curl --fail https://ms365.example.com/health
docker inspect --format '{{.State.Health.Status}}' e5-auto-renew
```

Before setup, protected APIs return `503 setup_required`. After setup, they return `401` without a valid bearer token. This is expected.
