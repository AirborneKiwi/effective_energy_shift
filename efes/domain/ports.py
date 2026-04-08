from efes.domain.models import EfesState
from efes_core.domain.ports import ObserverPort


class EfesObserverPort(ObserverPort):
    def on_step(self, state: EfesState) -> bool: ...