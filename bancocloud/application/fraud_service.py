"""Application orchestration for fraud evaluation.

Rules remain pure in ``engine.py``. Persistence and delivery are injected ports so
the same application service can run with local PostgreSQL or Azure adapters.
"""
from collections.abc import Callable

from bancocloud.contracts import validate
from bancocloud.engine import high_case_command, load_policy, score_event
from bancocloud.repositories.fraud import FraudEvaluationStore, HighCaseSink


class FraudContractError(ValueError):
    pass


class FraudService:
    def __init__(
        self,
        evaluation_store: FraudEvaluationStore,
        high_case_sink: HighCaseSink,
        policy_provider: Callable[[], dict] = load_policy,
    ):
        self.evaluation_store = evaluation_store
        self.high_case_sink = high_case_sink
        self.policy_provider = policy_provider

    def ingest(self, event: dict) -> dict:
        try:
            validate("transaction", event)
        except Exception as exc:
            raise FraudContractError("Transaction contract invalid") from exc

        policy = self.policy_provider()
        evaluation = self.evaluation_store.evaluate_once(
            event,
            lambda history: score_event(event, history, policy),
        )
        command = high_case_command(evaluation.score)
        if command is not None:
            # Replays intentionally publish again. The sink/case consumer must be
            # idempotent, which also recovers a failure after the score was saved.
            self.high_case_sink.publish_high_case(command)
        return {"score": evaluation.score, "replay": evaluation.replay}


__all__ = ["FraudContractError", "FraudService"]
