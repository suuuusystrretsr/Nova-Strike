from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ScheduledEvent:
    event_id: int
    due_time: float
    callback: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    session_id: Optional[int]


class SimulationScheduler:
    def __init__(self) -> None:
        self._events: List[ScheduledEvent] = []
        self._time = 0.0
        self._next_id = 1

    def clear(self) -> None:
        self._events = []
        self._time = 0.0
        self._next_id = 1

    def schedule(self, delay: float, callback: Callable[..., Any], *args, session_id: Optional[int] = None, **kwargs) -> int:
        delay_sec = max(0.0, float(delay))
        event = ScheduledEvent(
            event_id=self._next_id,
            due_time=self._time + delay_sec,
            callback=callback,
            args=tuple(args),
            kwargs=dict(kwargs),
            session_id=session_id,
        )
        self._next_id += 1
        self._events.append(event)
        return event.event_id

    def cancel(self, event_id: int) -> bool:
        for index, event in enumerate(self._events):
            if event.event_id == event_id:
                del self._events[index]
                return True
        return False

    def update(self, dt: float, current_session_id: Optional[int] = None) -> None:
        step = max(0.0, float(dt))
        if step <= 0.0:
            return
        self._time += step
        if not self._events:
            return

        due_events: List[ScheduledEvent] = []
        remaining: List[ScheduledEvent] = []
        for event in self._events:
            if event.due_time <= self._time:
                due_events.append(event)
            else:
                remaining.append(event)
        self._events = remaining

        due_events.sort(key=lambda e: (e.due_time, e.event_id))
        for event in due_events:
            if event.session_id is not None and current_session_id is not None and event.session_id != current_session_id:
                continue
            try:
                event.callback(*event.args, **event.kwargs)
            except Exception:
                # Keep simulation alive if a scheduled callback fails.
                continue

