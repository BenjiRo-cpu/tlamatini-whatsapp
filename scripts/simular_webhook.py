"""Envía un evento firmado al servidor local para probar el webhook sin Meta."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

secret = os.getenv("WHATSAPP_APP_SECRET", "secreto-local-cambialo")
url = os.getenv("LOCAL_WEBHOOK_URL", "http://127.0.0.1:5000/webhook")
payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "messages": [{
                    "from": "5215500000000",
                    "id": f"wamid.local.{int(time.time())}",
                    "timestamp": str(int(time.time())),
                    "type": "text",
                    "text": {"body": "¿Cómo funcionaban las chinampas?"},
                }],
            },
        }],
    }],
}
body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
response = requests.post(
    url,
    data=body,
    headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    timeout=10,
)
print(f"HTTP {response.status_code}: {response.text}")
