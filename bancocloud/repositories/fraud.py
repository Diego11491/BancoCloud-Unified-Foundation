"""Ports used by fraud processing independently of transport and persistence."""
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class FraudEvaluation:
    score: dict
    replay: bool


class FraudEvaluationStore(Protocol):
    def evaluate_once(
        self,
        event: dict,
        evaluator: Callable[[list[dict]], dict],
    ) -> FraudEvaluation: ...


class HighCaseSink(Protocol):
    def publish_high_case(self, command: dict) -> None: ...
