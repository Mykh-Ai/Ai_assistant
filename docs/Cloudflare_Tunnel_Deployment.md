# Cloudflare Tunnel deployment pins

Both VPS-n8n connectors use the official stable image:

```text
cloudflare/cloudflared:2026.10.4@sha256:4c72c1af2984a66a255efd20fc4ec73fe0f7267384b55315ad953b354b3361b4
```

The digest identifies the linux/amd64 manifest. The canonical callback config
is `docker-compose.prod.yml`. The canonical standalone OfficeFlow API config
is `deploy/officeflow-api.compose.yml`; it preserves the existing host-network
origin `127.0.0.1:8081` and read-only token-file mount. No token value belongs in
Git. The VPS copy was historically `/bot/officeflow-api.compose.yml`; keep it
aligned with this tracked source before any subsequent deployment.

Use the existing project names: **repo** for `cloudflared` and **bot** for
`officeflow_api_cloudflared`. Do not recreate the application services when
updating a connector.

```sh
docker compose -p repo -f docker-compose.prod.yml up -d --no-deps --no-build cloudflared
docker compose -p bot -f deploy/officeflow-api.compose.yml up -d --no-deps --no-build officeflow_api_cloudflared
```

The remotely managed OfficeFlow Tunnel may also carry the protected n8n
editor hostname. Preserve all existing ingress rules when adding a hostname;
do not replace the config with an n8n-only ingress list. Keep the callback
origin private at `http://bot:8081` and do not publish callback port 8081.

Before restarting a connector, retain direct SSH access and a root-only
launch/config/image backup. For reduced new-request interruption, start a
temporary connector with the same network and token mount, verify origin
reachability and `/ready`, then replace the canonical connector. For host
network replicas choose a separate loopback metrics port. Long-lived sessions
on the old process may still disconnect.

Acceptance requires version **2026.10.4** in the running process, expected
ingress received, four edge connections, preserved launch settings, and the
normal unauthenticated API/callback rejections. Do not disable TLS validation
to work around origin certificate errors.
