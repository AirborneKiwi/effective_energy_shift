from __future__ import annotations

import pickle
from pathlib import Path

from efes_core.domain.models import Results
from efes_core.domain.ports import ResultsRepositoryPort


class PickleResultsRepository(ResultsRepositoryPort):
    def save_results(self, results: Results, target: str) -> str:
        path = Path(target)
        if path.suffix != ".pickle":
            path = path.with_suffix(".pickle")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            pickle.dump(results, file)
        return str(path)

    def load_results(self, source: str) -> Results:
        path = Path(source)
        if path.suffix != ".pickle":
            path = path.with_suffix(".pickle")
        with path.open("rb") as file:
            return pickle.load(file)
