"""Fan-out of judge events to live subscribers (websocket clients)."""
import asyncio
import time
from collections import deque


class EventHub:
    def __init__(self, history: int = 100) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        # late joiners replay recent events, so a refreshed page is not blind
        self._history: deque[dict] = deque(maxlen=history)
        self._seq = 0

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        for event in self._history:
            queue.put_nowait(event)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict) -> None:
        self._seq += 1
        stamped = {**event, "seq": self._seq, "ts": round(time.time(), 3)}
        self._history.append(stamped)
        for queue in self._subscribers:
            queue.put_nowait(stamped)
