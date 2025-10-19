# Cryptolabs SSO Strategy (Nginx + Open WebUI + WordPress)

This document outlines the target SSO strategy after migrating from Caddy to Nginx, covering two supported approaches:

- Option A (recommended): OpenID Connect (OIDC) between Open WebUI and an IdP
- Option B: Trusted‑Header SSO using WordPress as the identity source via Nginx `auth_request`

Both options preserve existing services (LiteLLM, WPBM, Open WebUI) and ensure WebSockets and redirects function as before.

## Goals
- Seamless sign‑in for logged‑in WordPress users landing on `/ai-chat/`
- Preserve public endpoints and redirects
- Support secure, auditable SSO flow with minimal moving parts
- Keep LiteLLM and WPBM reachable behind Nginx

## High‑Level Architecture

- `webui.ai.cryptolabs.co.za` → Nginx → Open WebUI container (port 8080)
  - WebSockets at `/ws/socket.io`
  - HTTP to TLS redirect (80→443)
- `api.ai.cryptolabs.co.za` → Nginx → LiteLLM/API upstream (container IP:port)
- `wpbm.ai.cryptolabs.co.za` → Nginx → WPBM on 127.0.0.1:7777
- `www.cryptolabs.co.za/ai-chat/` → redirect to `https://webui.ai.cryptolabs.co.za/auth?redirect=%2F`

## Option A: OIDC (Recommended)
Open WebUI natively supports OIDC/OAuth2. This decouples WordPress from auth enforcement and avoids header‑level coupling.

- WebUI env (container/service):
  - `WEBUI_URL=https://webui.ai.cryptolabs.co.za`
  - `OPENID_PROVIDER_URL=<IdP discovery URL>`
  - `OAUTH_CLIENT_ID=<client_id>`
  - `OAUTH_CLIENT_SECRET=<client_secret>`
  - `OPENID_REDIRECT_URI=https://webui.ai.cryptolabs.co.za/oauth/oidc/callback`
  - Optional: `OAUTH_SCOPES=openid email profile`
  - Optional: `OAUTH_TOKEN_ENDPOINT_AUTH_METHOD=client_secret_post`
  - Optional: `OAUTH_CODE_CHALLENGE_METHOD=S256`
  - Optional: `WEBUI_AUTH_SIGNOUT_REDIRECT_URL=https://www.cryptolabs.co.za/ai-chat/`
- Nginx site (WebUI):
  - Proxy `/` to container IP:8080
  - Proxy `/ws/socket.io` with Upgrade/Connection headers
  - Optionally force SSO by redirecting `/auth` → `/oauth/oidc/login`

Pros:
- Standard flow, no WordPress coupling
- Clear logout behavior (end_session) supported
- Least custom logic at the proxy

## Option B: Trusted‑Header SSO via WordPress (Nginx auth_request)
Nginx acts as a “forward auth” proxy using `auth_request` to a WordPress REST endpoint that validates the session and returns user headers.

- WordPress endpoint (already in plugin): `/wp-json/cryptolabs/v1/webui/auth`
  - On success, returns headers:
    - `X-Webui-Email: <email>` (required)
    - `X-Webui-Name: <display_name>` (optional)
    - `X-User-Api-Key: <per-user key>` (optional)
    - `X-User-Litellm-Url: https://api.ai.cryptolabs.co.za/v1` (optional)
- WebUI env:
  - `WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Webui-Email`
  - Optional: `WEBUI_AUTH_TRUSTED_NAME_HEADER=X-Webui-Name`
  - Optional: `WEBUI_AUTH_TRUSTED_API_KEY_HEADER=X-User-Api-Key`
  - Optional: `WEBUI_AUTH_TRUSTED_LITELLM_URL_HEADER=X-User-Litellm-Url`
- Nginx (WebUI) example:
  - In `server` for `webui.ai.cryptolabs.co.za`:
    - Define an internal location that proxies to WordPress auth endpoint, forwarding cookies
    - Use `auth_request` to call that internal location for protected locations
    - On success, capture upstream headers and re‑emit them to Open WebUI

Pros:
- Single sign‑on is tied to WordPress login state
- No need to manage an external IdP

Notes:
- Remove any `/auth → /oauth/oidc/login` redirect in this mode
- Ensure WordPress cookies are forwarded in the `auth_request` call
- Keep the internal `auth_request` endpoint restricted (`internal;`)

## Migration From Caddy → Nginx

1) Stop and remove Caddy container (free ports 80/443)
2) Install Nginx + Certbot; enable Nginx
3) Create Nginx sites:
   - WebUI: proxy `/` and `/ws/socket.io` to container IP:8080; enable HTTPS
   - API: proxy `/` to LiteLLM/API upstream; enable HTTPS
   - WPBM: proxy `/` to 127.0.0.1:7777; enable HTTPS
   - WordPress host: include a snippet to redirect `/ai-chat` to WebUI auth
4) Obtain certificates with Certbot (`--nginx`)
5) Validate endpoints (HTTP 200/302, WebSockets 101)

## WordPress Plugin Alignment
- Plugin: Cryptolabs AI Gateway (>= 1.2.5)
- REST SSO endpoint implemented and tested
- AI Chat page uses `[cryptolabs_ai_chat]` shortcode
- Free credits and API settings configured in plugin settings

## LiteLLM Endpoint
- Public: `https://api.ai.cryptolabs.co.za/v1`
- Test:
  - `curl https://api.ai.cryptolabs.co.za/v1/chat/completions \`
  - `  -H "Content-Type: application/json" \`
  - `  -H "Authorization: Bearer <API_KEY>" \`
  - `  -d '{"model":"qwen3-coder-30b","messages":[{"role":"user","content":"Hello!"}]}'`
- In Trusted‑Header mode, per‑user keys can be pushed via `X-User-Api-Key`

## Redirects & WebSockets
- cryptolabs.co.za:/ai-chat → `https://webui.ai.cryptolabs.co.za/auth?redirect=%2F`
- WebSockets: `/ws/socket.io` proxied with Upgrade/Connection headers

## Testing Matrix
- Anonymous user → `/ai-chat/` shows login, no SSO
- Logged‑in user → `/ai-chat/` redirects to WebUI
- WebUI `/api/config`:
  - OIDC mode: `.oauth.providers.oidc` present
  - Trusted‑header mode: `.features.auth_trusted_header == true`
- WebSockets upgraded to 101 at `/ws/socket.io`
- LiteLLM `/v1/models` reachable (200/401)
- WPBM reachable at `https://wpbm.ai.cryptolabs.co.za/`

## Troubleshooting
- 443 connection refused → Nginx not bound / port conflict / firewall
- 502/504 from Nginx → wrong upstream IP:port or upstream not listening
- WebUI 500 → check container logs and SSO env variables
- SSO not triggering in Trusted‑Header mode → verify `auth_request` executes, headers propagate, and remove `/auth` → OIDC redirect

## Recommendation
Prefer Option A (OIDC) for standard auth with clear logout semantics. Use Option B (Trusted‑Header) when WordPress must remain the sole identity provider without introducing an IdP.

