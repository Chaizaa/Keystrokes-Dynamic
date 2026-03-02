You are GitHub Copilot. Help me implement a small standalone integration website (static single-page app) that demonstrates how to call my Flask API endpoints secured by HMAC using an API key and raw secret.

Context (server):
- Local Flask app runs at `http://localhost:5000`.
- Endpoints to call:
  - POST /api/v1/enroll
  - POST /api/v1/verify
- Authentication headers required:
  - `X-API-KEY`: api key string
  - `X-TIMESTAMP`: unix seconds integer
  - `X-API-SIGNATURE`: hex HMAC-SHA256 over `timestamp + body_bytes` using raw secret

Requirements for the site:
- Single static HTML file with minimal CSS and JavaScript (no build step).
- Use Web Crypto `SubtleCrypto` to compute HMAC-SHA256 from a user-provided raw secret.
- Provide inputs for: `api_key`, `api_secret` (raw), `user_id`, and `keystroke_data` (JSON array text area).
- Buttons to trigger `Enroll` and `Verify`. Each button:
  1. Serializes body to compact JSON (no added whitespace) exactly as sent.
  2. Generates `timestamp = Math.floor(Date.now()/1000)`.
  3. Computes `signature = HMAC_SHA256(raw_secret, timestamp_bytes + body_bytes)` and hex-encodes it.
  4. Sends fetch POST to the endpoint with required headers and body.
  5. Displays server response prettified in the page.
- Include clear instructions and a short troubleshooting note (timestamp window, CORS, run static server).

Deliverable file names: `dummy_client/index.html` and `dummy_client/README.md`.

Be concise and produce only the files requested.
