import asyncio
import json
import logging
from typing import Dict, Set, Any, AsyncGenerator, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PipelineEventBroadcaster:
    """
    In-memory async Pub/Sub event broadcaster for Server-Sent Events (SSE).
    Enables real-time streaming of document processing stages and pipeline telemetry.
    """
    def __init__(self):
        # Maps channel (e.g., 'global' or 'doc:{document_id}') to a set of subscriber queues
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str = "global") -> asyncio.Queue:
        """Register a subscriber queue for a specific channel."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = set()
            self._subscribers[channel].add(queue)
        logger.debug(f"Subscriber connected to channel: {channel}. Total subscribers: {len(self._subscribers[channel])}")
        return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue):
        """Remove a subscriber queue from a channel."""
        async with self._lock:
            if channel in self._subscribers:
                self._subscribers[channel].discard(queue)
                if not self._subscribers[channel]:
                    del self._subscribers[channel]
        logger.debug(f"Subscriber removed from channel: {channel}")

    def emit_sync(self, event_type: str, data: Dict[str, Any], channel: str = "global"):
        """
        Thread-safe synchronous emitter for background workers and sync services.
        Dispatches event into the active event loop without blocking.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data, channel), loop)
        else:
            # If no running event loop in current thread, attempt to get background event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data, channel), loop)
            except Exception as e:
                logger.warning(f"Failed to emit event {event_type} on channel {channel}: {e}")

    async def broadcast(self, event_type: str, data: Dict[str, Any], channel: str = "global"):
        """
        Broadcast an event to all subscribers of a channel and optionally to the global channel.
        """
        event_payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        async with self._lock:
            # Deliver to channel subscribers
            target_queues = list(self._subscribers.get(channel, set()))
            # If channel is not global, also deliver to global listeners
            if channel != "global":
                target_queues.extend(list(self._subscribers.get("global", set())))

        for q in target_queues:
            try:
                if q.full():
                    # Evict oldest item to prevent memory bloat on slow clients
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(event_payload)
            except Exception as e:
                logger.debug(f"Failed to queue event for subscriber on {channel}: {e}")

    async def stream_events(
        self,
        channel: str = "global",
        initial_events: Optional[list] = None,
        ping_interval_seconds: int = 15
    ) -> AsyncGenerator[str, None]:
        """
        Async generator formatting events into text/event-stream specification.
        Yields initial history first, followed by live events and periodic keep-alive pings.
        """
        # 1. Yield initial snapshot if provided
        if initial_events:
            for init_ev in initial_events:
                yield f"event: snapshot\ndata: {json.dumps(init_ev)}\n\n"

        queue = await self.subscribe(channel)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=ping_interval_seconds)
                    ev_type = event.get("event", "message")
                    ev_data = json.dumps(event.get("data", {}))
                    yield f"event: {ev_type}\ndata: {ev_data}\n\n"
                except asyncio.TimeoutError:
                    # SSE keepalive ping
                    yield ": ping\n\n"
        finally:
            await self.unsubscribe(channel, queue)

# Global singleton
event_broadcaster = PipelineEventBroadcaster()

