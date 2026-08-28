# Authentication session decision for 2.0.0

## Current token lifecycle

- `app/static/js/api.js` reads `ms365.access_token` from `localStorage`, writes it after login, removes it during logout/session failure, and sends it as an `Authorization: Bearer` header.
- `app/static/js/app.js` calls `setToken()` after a successful login and logout.
- Locale and theme also use `localStorage`, but are not credentials.

## Risk assessment

Any JavaScript that executes in the application origin could read the bearer token. The 2.0.0 browser policy reduces that exposure by allowing application scripts only from the same origin, serving pinned local assets, forbidding framing, forbidding arbitrary object/base sources, and avoiding runtime CDN scripts. CSP is defense in depth; it does not make `localStorage` equivalent to an HttpOnly cookie, and a same-origin script injection would remain high impact.

## Decision

Version 2.0.0 keeps the bearer-token design to avoid introducing an unreviewed cookie/CSRF migration during release packaging. The application uses a single-origin API, short bounded session lifetime, explicit logout, no-store API responses, and strict CSP. A future HttpOnly cookie change must include `Secure` in production, an appropriate `SameSite` policy, CSRF protection for state-changing requests, cookie deletion at logout, expiry/renewal behavior, OAuth popup coverage, and end-to-end regression tests before it replaces bearer authentication.
