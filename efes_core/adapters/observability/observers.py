from __future__ import annotations

from typing import Optional

from efes_core.domain.models import AlgorithmState
from efes_core.domain.ports import ObserverPort


def notify(observer: Optional[ObserverPort], state: AlgorithmState) -> bool:
    if observer is None:
        return False
    return bool(observer.on_step(state))


class NullObserver:
    def on_step(self, state: AlgorithmState) -> bool:
        return False

class CompositeObserver:
    def __init__(self, *observers) -> None:
        self._observers = list(observers)

    def on_step(self, state: AlgorithmState) -> bool:
        stop = False
        for observer in self._observers:
            stop = observer.on_step(state) or stop
        return stop