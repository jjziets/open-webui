from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def verify_trusted_signature(payload: str, signature: str, secret: str | bytes) -> bool:
    if not payload or not signature or not secret:
        return False

    secret_bytes = secret.encode() if isinstance(secret, str) else secret
    expected_signature = base64.b64encode(hmac.new(secret_bytes, payload.encode(), hashlib.sha256).digest()).decode()

    return hmac.compare_digest(expected_signature, signature)


def decode_trusted_payload(payload: str) -> dict[str, Any]:
    decoded = base64.b64decode(payload).decode()
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError('Trusted SSO payload must decode to an object')
    return data


def trusted_payload_is_fresh(
    payload_data: dict[str, Any],
    *,
    max_age_seconds: int = 900,
    now: int | None = None,
) -> bool:
    timestamp = int(payload_data.get('timestamp', 0) or 0)
    if not timestamp:
        return False

    current_time = int(time.time()) if now is None else now
    return abs(current_time - timestamp) <= max_age_seconds
