from __future__ import annotations

from pathlib import Path

from efes_core.adapters.scenarios.persistence import PickleResultsRepository
from efes_core.domain.models import Results, ParameterStudyResults
from efes_core.domain.ports import ParameterStudyStorePort

class FileParameterStudyStore(ParameterStudyStorePort):
    def __init__(self, result_dir: str, repository: PickleResultsRepository | None = None) -> None:
        self.result_dir = Path(result_dir)
        self.repository = repository or PickleResultsRepository()

    def prepare(self, parameter_variation, result_dir: str | None = None) -> None:
        if result_dir is not None:
            self.result_dir = Path(result_dir)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        parameter_variation.to_csv(self.result_dir / "basecases.csv", index=False)

    def _result_path(self, basecase: str) -> Path:
        return self.result_dir / basecase / "results.pickle"

    def exists(self, basecase: str) -> bool:
        return self._result_path(basecase).exists()

    def load_result_reference(self, basecase: str) -> str:
        return str(self._result_path(basecase))

    def save_result(self, basecase: str, results: Results) -> str:
        return self.repository.save_results(results, str(self._result_path(basecase)))

    def build_output(self, parameter_variation, results: list[str]) -> ParameterStudyResults:
        return ParameterStudyResults(parameter_variation=parameter_variation, results=results)
