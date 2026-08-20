# gs-protocol

JSON-RPC 2.0 envelope, NDJSON framing, numeric error codes.

Does **not** own method schemas (that is gs-registry) or mutate documents.

## Envelope

- `Request` — `{ jsonrpc:"2.0", id: string|number, method, params }`
- `Response` — ok `{ jsonrpc, id, result }` or err `{ jsonrpc, id, error }`
- `Notification` — `{ jsonrpc, method, params }` (no `id`; events)
- `error.code` is always a JSON number (`PARSE` … `BUSY`)
- `error.data.app_code` holds business codes (`E_PROTO`, `E_VALIDATION`, …)

## Framing

`encode_message` / `decode_message` / `read_ndjson_line` / `write_ndjson_line`

One UTF-8 object per line + LF. Cap `MAX_LINE_BYTES` (4MB). Over-cap or
missing LF → `-32600` / `E_PROTO` (caller closes). Top-level JSON arrays
→ `-32600`.
