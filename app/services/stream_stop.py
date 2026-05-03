import threading

_stop_events: dict[str, threading.Event] = {}


def register_stream(stream_id: str) -> threading.Event:
    event = threading.Event()
    _stop_events[stream_id] = event
    _sweep_stale()
    return event


def signal_stop(stream_id: str) -> bool:
    event = _stop_events.get(stream_id)
    if event:
        event.set()
        return True
    return False


def unregister_stream(stream_id: str) -> None:
    _stop_events.pop(stream_id, None)


def _sweep_stale() -> None:
    if len(_stop_events) > 1000:
        keys = list(_stop_events.keys())[:500]
        for key in keys:
            _stop_events.pop(key, None)
