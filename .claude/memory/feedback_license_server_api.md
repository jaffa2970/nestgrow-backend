---
name: License Server API — correct endpoints and formats
description: The real API paths and request formats for license.lake8.dev, discovered by reading the actual source code
type: feedback
originSessionId: 5c0ef111-b4c5-4ee2-83cd-505b4c18edbe
---
All endpoints are at the root — NO `/api/v1/` prefix (previous code used wrong prefix causing 404 everywhere).

**Why:** The LS FastAPI app mounts routers directly at root. The `/api/v1/` prefix was assumed from convention but doesn't exist.

**How to apply:** Always verify LS endpoints by reading `/home/tommy/Documenti/license-server/app/routers/` before writing any httpx calls. Key correct paths:
- `POST /register` (not `/api/v1/register`)
- `POST /heartbeat` (not `GET /api/v1/heartbeat` — it's a POST)
- `GET /notifications` (not `/api/v1/messages`)
- `GET /support/tickets` — auth via `Authorization: Bearer <jwt>` header only, NOT form-data token in body (for GET)
- `POST /support/tickets` — Bearer header OR `token` field in JSON body (both accepted)

**Field names:** `prodotto_codice` (not `prodotto`), `oggetto`/`testo` for tickets (not `titolo`/`corpo`).
