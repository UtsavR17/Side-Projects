"""SSE event hub.

Pipeline processes publish to the Redis `events` channel; the API's /api/events
endpoint streams them to browsers. With no Redis (local dev) the stream sends
heartbeats only — same-process publishes are also supported for tests.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from app.cache import cache

logger = logging.getLogger(__name__)

CHANNEL = "events"
HEARTBEAT_SECONDS = 15


async def event_stream():
    """Yield `data: {...}` SSE frames forever."""
    pubsub = cache.pubsub()
    if pubsub is None:
        while True:
            yield f": heartbeat {int(time.time())}\n\n"
            await asyncio.sleep(HEARTBEAT_SECONDS)
        return

    try:
        pubsub.subscribe(CHANNEL)
        while True:
            message = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"
            else:
                yield f": heartbeat {int(time.time())}\n\n"
                await asyncio.sleep(HEARTBEAT_SECONDS)
    finally:
        try:
            pubsub.close()
        except Exception:  # noqa: BLE001
            pass


def publish_event(event: dict) -> None:
    cache.publish(CHANNEL, event)
