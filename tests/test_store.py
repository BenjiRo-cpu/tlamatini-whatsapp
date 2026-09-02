from tlamatini.store import SQLiteStore


def test_state_history_and_idempotency(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    assert store.claim_message("wamid.1")
    assert not store.claim_message("wamid.1")
    store.complete_message("wamid.1")
    assert not store.claim_message("wamid.1")

    store.update_state("52155", mode="normal", current_topic="chinampas")
    assert store.get_state("52155")["current_topic"] == "chinampas"
    store.append_message("52155", "user", "Hola")
    store.append_message("52155", "assistant", "¡Hola!")
    assert len(store.recent_messages("52155")) == 2


def test_failed_message_can_retry(tmp_path):
    store = SQLiteStore(str(tmp_path / "test.db"))
    assert store.claim_message("wamid.error")
    store.fail_message("wamid.error", "timeout")
    assert store.claim_message("wamid.error")
