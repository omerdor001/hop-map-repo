import asyncio

_sse_queues: dict[str, list[asyncio.Queue]] = {}
_SSE_SHUTDOWN = object()


def register_listener(child_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(child_id, []).append(q)
    return q


def unregister_listener(child_id: str, q: asyncio.Queue) -> None:
    _sse_queues[child_id].remove(q)
    if not _sse_queues[child_id]:
        del _sse_queues[child_id]


async def broadcast(child_id: str, payload: dict) -> None:
    for q in _sse_queues.get(child_id, []):
        await q.put(payload)


async def shutdown_all() -> None:
    for queues in list(_sse_queues.values()):
        for q in queues:
            await q.put(_SSE_SHUTDOWN)
