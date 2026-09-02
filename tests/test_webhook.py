import hashlib
import hmac
import json
from dataclasses import replace

from tlamatini.app import Services, create_app
from tlamatini.config import Config
from tlamatini.store import SQLiteStore


class FakeAgent:
    def __init__(self):
        self.calls = []

    def respond(self, user_id, text):
        self.calls.append((user_id, text))
        return "Respuesta de prueba"


class FakeWhatsApp:
    def __init__(self):
        self.sent = []

    def send_text(self, recipient, text):
        self.sent.append((recipient, text))
        return {"messages": [{"id": "out.1"}]}


def make_app(tmp_path):
    config = replace(
        Config(),
        database_path=str(tmp_path / "webhook.db"),
        whatsapp_verify_token="token-prueba",
        whatsapp_app_secret="app-secret",
        verify_webhook_signature=True,
        process_messages_async=False,
    )
    store = SQLiteStore(config.database_path)
    agent = FakeAgent()
    whatsapp = FakeWhatsApp()
    app = create_app(config, Services(store, agent, whatsapp))
    app.testing = True
    return app, store, agent, whatsapp


def payload(message_id="wamid.1"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{
            "from": "5215512345678", "id": message_id, "type": "text",
            "text": {"body": "¿Qué eran las chinampas?"}
        }]}}]}],
    }


def signature(body, secret="app-secret"):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_verification(tmp_path):
    app, *_ = make_app(tmp_path)
    client = app.test_client()
    response = client.get("/webhook?hub.mode=subscribe&hub.verify_token=token-prueba&hub.challenge=12345")
    assert response.status_code == 200
    assert response.text == "12345"


def test_message_flow_and_duplicate_protection(tmp_path):
    app, _, agent, whatsapp = make_app(tmp_path)
    client = app.test_client()
    raw = json.dumps(payload(), separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature(raw)}

    first = client.post("/webhook", data=raw, headers=headers)
    second = client.post("/webhook", data=raw, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(agent.calls) == 1
    assert whatsapp.sent == [("5215512345678", "Respuesta de prueba")]


def test_invalid_signature_is_rejected(tmp_path):
    app, *_ = make_app(tmp_path)
    response = app.test_client().post(
        "/webhook", json=payload(), headers={"X-Hub-Signature-256": "sha256=bad"}
    )
    assert response.status_code == 403
