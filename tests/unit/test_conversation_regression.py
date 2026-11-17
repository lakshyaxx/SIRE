"""Conversation/provenance negative controls; provider fixtures here are explicitly test-only."""

import asyncio
import json
import pytest
from app.chat.conversation import fast_route, history_turns, input_audio, describe
from app.chat.service import ChatService
from app.evidence.context import compact, restore_text
from app.evidence.ledger import Ledger
from app.core.errors import SireError


def test_stop_interrupts_upstream_read_before_the_first_token():
    from app.providers.adapter import _lines

    async def run():
        entered, closed, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class TestOnlyResponse:
            async def aiter_lines(self):
                entered.set()
                try:
                    await asyncio.Future()
                    yield "unreachable test-only line"
                finally:
                    closed.set()

        iterator = _lines(TestOnlyResponse(), stopped)
        task = asyncio.create_task(anext(iterator))
        await entered.wait()
        stopped.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        await iterator.aclose()
        assert closed.is_set()

    asyncio.run(run())


@pytest.mark.parametrize(
    "question",
    [
        "hi",
        "Hello?",
        "Hey SIRE!",
        "Good evening",
        "I want to talk to you, give me some answers, bro.",
    ],
)
def test_social_route_is_transport_independent_and_not_a_phrase_specific_model_patch(
    question,
):
    assert fast_route(question) == "social"
    assert fast_route(question + " Tell me the measured pressure of my pump.") is None


def test_empty_evidence_never_instructs_the_model_to_invent_an_alias():
    context, mapping = compact([], "Tell me a short story")
    assert not mapping and "[E1]" not in context["citation_format"]
    assert "not required" in context["citation_format"]
    assert restore_text("We can talk without citations.", {})
    with pytest.raises(SireError):
        restore_text("This is an observed result [E1].", {})


def test_capabilities_use_actual_resolvable_manifest_without_inventing_the_acronym(
    store,
):
    assert fast_route("Can you explain to me what SIRE is all about?") == "overview"
    assert fast_route("How does your hypothesis engine work?") == "hypotheses"
    assert fast_route("What does SIRE recommend for bearing damage?") is None
    text, evidence = describe(store, "overview")
    resolved = Ledger(store).resolve(evidence.id)["evidence"]
    assert resolved["pointer"]["path"] == "config/capabilities.yaml"
    assert resolved["observation"]["text"] in text
    assert "Simulated Intelligent Reasoning Engine" not in text


def test_failed_and_unpaired_history_cannot_contaminate_new_prompts():
    rows = [
        {
            "role": "user",
            "content": "failed question",
            "status": "complete",
            "metadata": {},
        },
        {"role": "assistant", "content": "[E999]", "status": "error", "metadata": {}},
        {
            "role": "user",
            "content": "My name is Sam",
            "status": "complete",
            "metadata": {},
        },
        {
            "role": "assistant",
            "content": "Hello Sam [E1]",
            "status": "complete",
            "metadata": {"evidence": [{"modality": "audio"}]},
        },
    ]
    turns = history_turns(rows)
    assert len(turns) == 2 and turns[-1]["content"] == "Hello Sam "
    assert "failed question" not in json.dumps(turns)


def test_audio_input_is_scoped_provenance_not_independent_evidence(store):
    cid = store.create_conversation()["id"]
    metadata = {
        "transcript": {
            "text": "Hello?",
            "model": "TEST-ONLY-ASR",
            "provider": "TEST-ONLY",
        }
    }
    with store.connection() as db:
        db.execute(
            "INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "test-only-audio",
                cid,
                "test-only.wav",
                "audio",
                "audio/wav",
                "test-only-hash",
                "test-only-no-disk-file",
                json.dumps(metadata),
                "2026-01-01T00:00:00Z",
            ),
        )
    attachment = store.attachment("test-only-audio", cid)
    selected, provenance = input_audio(
        store, cid, [attachment], "Hello?", attachment["id"], True
    )
    assert not selected and provenance["transcript_unverified"]
    assert input_audio(store, cid, [attachment], "Analyze this recording", None, False)[
        0
    ] == [attachment]
    other = store.create_conversation()["id"]
    with pytest.raises(SireError):
        input_audio(store, other, [], "Hello?", attachment["id"], True)


def test_social_and_documented_answers_bypass_models_even_after_failed_source_turns(
    store, provider
):
    cid = store.create_conversation()["id"]
    store.add_message(cid, "user", "Test-only old failure")
    store.add_message(
        cid,
        "assistant",
        "",
        "error",
        {"evidence": [{"id": "E999", "modality": "audio"}]},
    )

    async def run():
        service = ChatService(store, provider)
        for index, question in enumerate(
            ["hi", "What is SIRE?", "How does your hypothesis engine work?"]
        ):
            events = [
                e
                async for e in service.events(
                    cid, f"test-only-{index}", question, [], "chat", None, None, False
                )
            ]
            assert events[-1]["status"] == "complete"
            assert events[-1]["metadata"]["model_activity"] == []
            assert (
                events[-1]["metadata"]["orchestration"]["intent"] == "fast_conversation"
            )

    asyncio.run(run())
    assert not provider.requests


def test_plain_conversation_and_engineering_still_reject_fabricated_references(
    store, provider
):
    cid = store.create_conversation()["id"]

    async def run():
        service = ChatService(store, provider)
        events = [
            e
            async for e in service.events(
                cid,
                "test-only-plain",
                "Tell me a short story",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]
        assert events[-1]["status"] == "complete"
        assert "[E1]" not in json.dumps(provider.requests[-1])

        async def invalid(*args):
            yield "The pressure was measured at 100 bar [E99]."

        provider.stream = invalid
        events = [
            e
            async for e in service.events(
                cid,
                "test-only-false",
                "What was the measured pressure?",
                [],
                "chat",
                None,
                None,
                False,
            )
        ]
        assert events[-1]["status"] == "error"
        assert events[-1]["metadata"]["error"]["code"] == "unsupported_source_reference"
        assert not any(e["type"] == "delta" for e in events)

    asyncio.run(run())
