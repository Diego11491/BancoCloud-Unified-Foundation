import unittest
from uuid import uuid4

from bancocloud.application.cases_service import CaseContractError, CaseReferenceError, CasesService


class FakeCases:
    def __init__(self):
        self.case_id = uuid4()
        self.transaction_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.saved = None

    def list_recent(self, limit=100):
        return [{"case_id": str(self.case_id), "evidence": {"risk_level": "HIGH"}}]

    def get_reference(self, case_id):
        return (self.transaction_id, self.correlation_id) if case_id == self.case_id else None

    def save_decision(self, case_id, decision):
        self.saved = (case_id, decision)


class CasesServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeCases()
        self.service = CasesService(self.repo)
        self.decision = {
            "schema_version": "1.0",
            "case_id": str(self.repo.case_id),
            "transaction_id": self.repo.transaction_id,
            "decision": "INCONCLUSIVE",
            "decided_at": "2026-09-27T16:00:00-05:00",
            "analyst_ref": "synthetic-analyst-01",
            "correlation_id": self.repo.correlation_id,
        }

    def test_lists_existing_cases(self):
        self.assertEqual(self.service.list_cases()[0]["case_id"], str(self.repo.case_id))

    def test_records_a_contract_valid_decision(self):
        self.assertEqual(self.service.record_decision(self.repo.case_id, self.decision), {"status": "recorded"})
        self.assertEqual(self.repo.saved, (self.repo.case_id, self.decision))

    def test_rejects_invalid_contract_and_cross_case_reference(self):
        with self.assertRaises(CaseContractError):
            self.service.record_decision(self.repo.case_id, {**self.decision, "decision": "BLOCK_ACCOUNT"})
        with self.assertRaises(CaseReferenceError):
            self.service.record_decision(uuid4(), self.decision)


if __name__ == "__main__":
    unittest.main()
