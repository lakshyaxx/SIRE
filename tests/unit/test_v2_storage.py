"""Persistence, ownership boundaries and explicit deletion confirmation."""

import pytest
from app.core.errors import SireError
from app.storage.database import Store


def test_restart_and_rename(store):
    c = store.create_conversation()
    store.add_message(c["id"], "user", "test-only retained note")
    store.rename(c["id"], "Renamed session")
    reopened = Store(store.path)
    assert reopened.conversation(c["id"])["title"] == "Renamed session"
    assert reopened.messages(c["id"])[0]["content"] == "test-only retained note"


def test_delete_requires_confirmation(store):
    c = store.create_conversation()
    with pytest.raises(SireError):
        store.delete(c["id"], False)
    assert store.conversation(c["id"])
    store.delete(c["id"], True)
    with pytest.raises(SireError):
        store.conversation(c["id"])


def test_results_cannot_select_arbitrary_table(store):
    with pytest.raises(ValueError):
        store.save_result("conversations;DROP TABLE messages", {})
    result = {"test_only": True}
    identifier = store.save_result("predictions", result)
    assert store.result("predictions", identifier)["test_only"] is True
