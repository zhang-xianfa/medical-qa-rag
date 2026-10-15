import asyncio
import json
from typing import AsyncIterator


async def sse_event_generator(stream: AsyncIterator[str], event_type: str, **metadata) -> AsyncIterator[str]:
    async for token in stream:
        payload = {"type": event_type, "content": token}
        payload.update(metadata)
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def heartbeat_generator(interval: float = 15.0) -> AsyncIterator[str]:
    while True:
        await asyncio.sleep(interval)
        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"


async def merge_streams(*streams: AsyncIterator[str]) -> AsyncIterator[str]:
    async def _wrap(stream, queue):
        async for item in stream:
            await queue.put(item)

    queue: asyncio.Queue = asyncio.Queue()
    tasks = [asyncio.create_task(_wrap(s, queue)) for s in streams]
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield item
            except asyncio.TimeoutError:
                break
    finally:
        for task in tasks:
            task.cancel()
