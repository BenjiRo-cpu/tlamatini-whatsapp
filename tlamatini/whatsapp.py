from __future__ import annotations

from dataclasses import dataclass
import logging

import requests


LOGGER = logging.getLogger(__name__)


@dataclass
class WhatsAppClient:
    access_token: str
    phone_number_id: str
    api_version: str = "v25.0"
    timeout: int = 20
    dry_run: bool = False

    def send_text(self, recipient: str, text: str) -> dict:
        if self.dry_run:
            LOGGER.info("WhatsApp dry-run para %s: %s", recipient, text)
            return {"dry_run": True, "to": recipient, "text": text}
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("WhatsApp no está configurado: faltan access token o phone number ID")
        response = requests.post(
            f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4096]},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def extract_messages(payload: dict) -> list[dict[str, str]]:
    extracted: list[dict[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                item = {
                    "id": message.get("id", ""),
                    "from": message.get("from", ""),
                    "type": message.get("type", "unknown"),
                    "text": "",
                }
                if item["type"] == "text":
                    item["text"] = message.get("text", {}).get("body", "").strip()
                extracted.append(item)
    return [item for item in extracted if item["id"] and item["from"]]
