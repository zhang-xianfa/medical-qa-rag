import json
import pytest
from llm.streaming import sse_event_generator, heartbeat_generator, merge_streams


async def _token_stream(tokens):
    for t in tokens:
        yield t


@pytest.mark.asyncio
async def test_sse_event_generator_produces_valid_sse_format():
    stream = _token_stream(["你好", "世界"])
    lines = []
    async for line in sse_event_generator(stream, "message", role="assistant"):
        lines.append(line)
    assert len(lines) == 2
    assert lines[0].startswith("data: ")
    assert lines[0].endswith("\n\n")
    payload = json.loads(lines[0][6:].strip())
    assert payload["type"] == "message"
    assert payload["content"] == "你好"
    assert payload["role"] == "assistant"


@pytest.mark.asyncio
async def test_sse_event_generator_handles_empty_stream():
    stream = _token_stream([])
    lines = []
    async for line in sse_event_generator(stream, "diagnosis_complete"):
        lines.append(line)
    assert lines == []


@pytest.mark.asyncio
async def test_heartbeat_generator_emits_at_interval():
    gen = heartbeat_generator(interval=0.01)
    beats = []
    async for line in gen:
        beats.append(line)
        if len(beats) >= 2:
            break
    assert len(beats) == 2
    for beat in beats:
        payload = json.loads(beat[6:].strip())
        assert payload["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_merge_streams_interleaves_correctly():
    async def stream_a():
        yield "a1"
        yield "a2"

    async def stream_b():
        yield "b1"

    results = []
    async for item in merge_streams(stream_a(), stream_b()):
        results.append(item)
    assert len(results) == 3
    assert set(results) == {"a1", "a2", "b1"}
