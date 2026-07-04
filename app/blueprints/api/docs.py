"""
Interactive API documentation (Swagger UI) for the partner API.

Routes
------
GET /api/docs          — Swagger UI page (interactive tester)
GET /api/openapi.json  — OpenAPI 3.0 spec for the API-key endpoints

Cakupan spec ini sengaja dibatasi ke endpoint yang di-*authenticate* dengan
**API key** (``/api/partner/*``) — itulah yang ingin diuji lewat Swagger.
Di Swagger UI: tekan tombol **Authorize**, tempel API key kamu (tanpa awalan
``Bearer``), lalu pakai "Try it out".

Tidak menambah dependency: spec berupa dict Python, Swagger UI dimuat dari CDN.
"""

from __future__ import annotations

from flask import jsonify, render_template_string

from ._shared import api_bp


# ---------------------------------------------------------------------------
# Contoh sampel keystroke yang valid (mengetik "test") — bisa langsung dipakai
# di "Try it out". Tiap event: {code, key, evt: d|u, t: milidetik}.
# ---------------------------------------------------------------------------
_EXAMPLE_EVENTS = [
    {"code": "KeyT", "key": "t", "evt": "d", "t": 0},
    {"code": "KeyT", "key": "t", "evt": "u", "t": 90},
    {"code": "KeyE", "key": "e", "evt": "d", "t": 160},
    {"code": "KeyE", "key": "e", "evt": "u", "t": 250},
    {"code": "KeyS", "key": "s", "evt": "d", "t": 320},
    {"code": "KeyS", "key": "s", "evt": "u", "t": 410},
    {"code": "KeyT", "key": "t", "evt": "d", "t": 480},
    {"code": "KeyT", "key": "t", "evt": "u", "t": 570},
]


OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Identitype Partner API",
        "version": "1.0.0",
        "description": (
            "API keystroke-dynamics untuk partner. Semua endpoint di sini "
            "di-autentikasi dengan **API key** lewat header "
            "`Authorization: Bearer <api_key>`.\n\n"
            "**Alur pemakaian:**\n"
            "1. `POST /api/partner/enroll` — kirim minimal **10 sampel** keystroke "
            "untuk satu `username` (panggil berulang).\n"
            "2. Setelah 10 sampel, model per-user dilatih otomatis di background.\n"
            "3. `POST /api/partner/verify` — verifikasi ritme ketikan. Jika model "
            "masih dilatih, response `202`; cukup retry beberapa detik lagi.\n\n"
            "Klik **Authorize** dan tempel API key kamu untuk mulai menguji."
        ),
    },
    "servers": [{"url": "/", "description": "Server saat ini"}],
    "tags": [
        {"name": "Partner", "description": "Enrollment & verification via API key"},
    ],
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Tempel API key kamu di sini (tanpa kata 'Bearer').",
            }
        },
        "schemas": {
            "KeystrokeEvent": {
                "type": "object",
                "required": ["code", "key", "evt", "t"],
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "KeyT",
                        "description": "KeyboardEvent.code (tombol fisik)",
                    },
                    "key": {
                        "type": "string",
                        "example": "t",
                        "description": "Karakter yang dihasilkan tombol",
                    },
                    "evt": {
                        "type": "string",
                        "enum": ["d", "u"],
                        "description": "d = keydown, u = keyup",
                    },
                    "t": {
                        "type": "integer",
                        "example": 0,
                        "description": "Timestamp dalam milidetik",
                    },
                },
            },
            "EnrollRequest": {
                "type": "object",
                "required": ["username", "events"],
                "properties": {
                    "username": {"type": "string", "maxLength": 64, "example": "budi"},
                    "email": {
                        "type": "string",
                        "nullable": True,
                        "example": "budi@example.com",
                    },
                    "events": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/KeystrokeEvent"},
                    },
                },
                "example": {
                    "username": "budi",
                    "email": "budi@example.com",
                    "events": _EXAMPLE_EVENTS,
                },
            },
            "VerifyRequest": {
                "type": "object",
                "required": ["username", "events"],
                "properties": {
                    "username": {"type": "string", "maxLength": 64, "example": "budi"},
                    "events": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/KeystrokeEvent"},
                    },
                },
                "example": {"username": "budi", "events": _EXAMPLE_EVENTS},
            },
            "EnrollResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "message": {"type": "string", "example": "Sample 1/10 saved"},
                    "enrollment_id": {"type": "string", "example": "enr_1_5"},
                    "username": {"type": "string", "example": "budi"},
                    "progress": {
                        "type": "object",
                        "properties": {
                            "current": {"type": "integer", "example": 1},
                            "target": {"type": "integer", "example": 10},
                            "complete": {"type": "boolean", "example": False},
                        },
                    },
                    "remaining_quota": {"type": "integer", "example": 99},
                },
            },
            "VerifyResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "verified": {"type": "boolean", "example": True},
                    "decision": {
                        "type": "string",
                        "enum": ["genuine", "impostor"],
                        "example": "genuine",
                    },
                    "username": {"type": "string", "example": "budi"},
                    "confidence_score": {"type": "number", "format": "float", "example": 0.87},
                    "confidence_label": {"type": "string", "example": "High Confidence"},
                    "threshold": {"type": "number", "format": "float", "example": 0.7},
                    "method": {"type": "string", "example": "svm"},
                },
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "message": {"type": "string", "example": "Invalid API key"},
                    "error_code": {"type": "string", "example": "UNAUTHORIZED"},
                },
            },
        },
    },
    "security": [{"bearerAuth": []}],
    "paths": {
        "/api/partner/enroll": {
            "post": {
                "tags": ["Partner"],
                "summary": "Kirim satu sampel keystroke (enrollment)",
                "description": (
                    "Menyimpan satu sampel keystroke untuk `username`. Ulangi minimal "
                    "**10x** untuk username yang sama agar model bisa dilatih otomatis."
                ),
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/EnrollRequest"}
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Sampel tersimpan",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/EnrollResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Field kurang / data keystroke tidak valid",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "401": {
                        "description": "API key tidak valid",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "403": {"description": "Origin tidak diizinkan untuk API key ini"},
                    "429": {"description": "Rate limit terlampaui"},
                },
            }
        },
        "/api/partner/verify": {
            "post": {
                "tags": ["Partner"],
                "summary": "Verifikasi sampel keystroke",
                "description": (
                    "Memverifikasi ritme ketikan lewat model per-user. Membutuhkan "
                    "**≥10 sampel enrollment** lebih dulu. Jika model masih dilatih, "
                    "response `202` (retry beberapa detik lagi)."
                ),
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/VerifyRequest"}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Hasil verifikasi (lihat field `verified`)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/VerifyResponse"}
                            }
                        },
                    },
                    "202": {"description": "Model masih dilatih — retry beberapa detik lagi"},
                    "400": {"description": "Data keystroke tidak valid"},
                    "401": {"description": "API key tidak valid"},
                    "404": {"description": "Sampel enrollment belum cukup (<10)"},
                    "403": {"description": "Origin tidak diizinkan untuk API key ini"},
                    "429": {"description": "Rate limit terlampaui"},
                },
            }
        },
    },
}


_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Identitype Partner API — Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script {% if csp_nonce is defined %}nonce="{{ csp_nonce() }}"{% endif %}>
    window.onload = function () {
      window.ui = SwaggerUIBundle({
        url: "/api/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    };
  </script>
</body>
</html>"""


@api_bp.route("/openapi.json", methods=["GET"])
def openapi_spec():
    """Return the OpenAPI 3.0 spec as JSON."""
    return jsonify(OPENAPI_SPEC)


@api_bp.route("/docs", methods=["GET"])
def swagger_ui():
    """Serve the interactive Swagger UI page."""
    return render_template_string(_SWAGGER_HTML)
