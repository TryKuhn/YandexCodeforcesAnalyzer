"""Event hub: fan-out, history replay, unsubscribe."""
from app.hub import EventHub


async def test_subscriber_receives_published_events():
    hub = EventHub()
    queue = hub.subscribe()

    hub.publish({"type": "job.queued", "job_id": "a"})

    event = queue.get_nowait()
    assert event["type"] == "job.queued"
    assert event["seq"] == 1
    assert "ts" in event


async def test_all_subscribers_get_every_event():
    hub = EventHub()
    first, second = hub.subscribe(), hub.subscribe()

    hub.publish({"type": "x"})

    assert first.get_nowait()["type"] == "x"
    assert second.get_nowait()["type"] == "x"


async def test_late_subscriber_replays_history():
    hub = EventHub()
    hub.publish({"type": "early"})

    queue = hub.subscribe()

    assert queue.get_nowait()["type"] == "early"


async def test_history_is_bounded():
    hub = EventHub(history=3)
    for i in range(10):
        hub.publish({"type": "e", "i": i})

    queue = hub.subscribe()

    replayed = [queue.get_nowait()["i"] for _ in range(queue.qsize())]
    assert replayed == [7, 8, 9]


async def test_unsubscribed_queue_stops_receiving():
    hub = EventHub()
    queue = hub.subscribe()
    hub.unsubscribe(queue)

    hub.publish({"type": "x"})

    assert queue.qsize() == 0
