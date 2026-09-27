from uuid import UUID

from bancocloud.contracts import validate
from bancocloud.repositories.cases import CaseRepository


class CaseContractError(ValueError):
    pass


class CaseReferenceError(ValueError):
    pass


class CasesService:
    def __init__(self, repository: CaseRepository):
        self.repository = repository

    def list_cases(self, limit: int = 100) -> list[dict]:
        return self.repository.list_recent(limit)

    def record_decision(self, case_id: UUID, decision: dict) -> dict:
        try:
            validate("decision", decision)
        except Exception as exc:
            raise CaseContractError("Analyst decision contract invalid") from exc
        if decision["case_id"] != str(case_id):
            raise CaseReferenceError("Case ID mismatch")
        reference = self.repository.get_reference(case_id)
        if not reference or reference != (decision["transaction_id"], decision["correlation_id"]):
            raise CaseReferenceError("Case reference mismatch")
        self.repository.save_decision(case_id, decision)
        return {"status": "recorded"}
