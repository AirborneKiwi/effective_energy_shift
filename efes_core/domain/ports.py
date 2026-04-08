from typing import List

from typing import Protocol

from efes_core.domain.models import EnergyPacket, AnalysisResults, Results, ParameterStudyResults, AlgorithmState


class EfesImplementationPort(Protocol):
    def execute(self) -> List[EnergyPacket]: ...

    def initialize(self, analysis_results: AnalysisResults) -> None: ...


class ObserverPort(Protocol):
    def on_step(self, state: AlgorithmState) -> bool: ...


class ResultsRepositoryPort(Protocol):
    def save_results(self, results: Results, target: str) -> str:
        ...

    def load_results(self, source: str) -> Results:
        ...


class ParameterStudyStorePort(Protocol):
    def prepare(self, parameter_variation, result_dir: str | None = None) -> None:
        ...

    def exists(self, basecase: str) -> bool:
        ...

    def load_result_reference(self, basecase: str) -> str:
        ...

    def save_result(self, basecase: str, results: Results) -> str:
        ...

    def build_output(self, parameter_variation, results: list[str]) -> ParameterStudyResults:
        ...
