import copy
import json
import unittest
from uuid import uuid4

from bancocloud.application.genai_service import GenAIService, PROMPT_VERSION
from bancocloud.contracts import validate


def evidence():
    return {
        "schema_version": "1.0",
        "command_id": str(uuid4()),
        "transaction_id": str(uuid4()),
        "risk_score": 0.91,
        "risk_level": "HIGH",
        "reason_codes": ["NEW_DEVICE", "AMOUNT_SPIKE"],
        "model_version": "rules-only-v1",
        "policy_version": "student-rules-v2",
        "correlation_id": str(uuid4()),
        "created_at": "2026-09-27T12:00:00Z",
    }


class FakeProvider:
    name = "fake-provider"
    model = "fake-model-v1"

    def __init__(self, output=None, error=None):
        self.output, self.error, self.prompt = output, error, None

    def generate(self, prompt):
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.output


def model_output(code="NEW_DEVICE"):
    return {
        "summary": "La evidencia contiene señales que requieren revisión humana.",
        "signal_explanations": [{"code": code, "explanation": "Señal registrada por la política."}],
        "missing_information": ["Confirmación del cliente no disponible."],
        "recommended_next_steps": ["Revisar evidencia en fuentes gobernadas."],
        "limitations": ["No constituye una decisión."],
    }


class GenAIServiceTests(unittest.TestCase):
    def test_local_output_is_auditable_and_contract_valid(self):
        result = GenAIService().summarize(uuid4(), evidence())
        self.assertEqual(result["generation_mode"], "LOCAL_DETERMINISTIC")
        self.assertEqual(result["prompt_version"], PROMPT_VERSION)
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["decision_authority"], "HUMAN_ANALYST")
        self.assertTrue(result["input_reference"].startswith("sha256:"))
        validate("genai_summary", result)

    def test_prompt_contains_only_versioned_envelope_and_case_evidence(self):
        provider = FakeProvider(model_output())
        case = evidence()
        GenAIService(provider).summarize(uuid4(), case)
        envelope = json.loads(provider.prompt.split("INPUT_JSON:\n", 1)[1])
        self.assertEqual(envelope["prompt_version"], PROMPT_VERSION)
        self.assertEqual(envelope["evidence"], case)
        self.assertEqual(set(envelope), {"prompt_version", "case_id", "input_reference", "evidence"})

    def test_case_contract_rejects_extra_pii_field(self):
        case = evidence()
        case["customer_email"] = "person@example.com"
        with self.assertRaises((ValueError, Exception)):
            GenAIService().summarize(uuid4(), case)

    def test_reason_code_with_sensitive_data_is_rejected(self):
        case = evidence()
        case["reason_codes"] = ["CONTACT_person@example.com"]
        with self.assertRaises(ValueError):
            GenAIService().summarize(uuid4(), case)

    def test_model_cannot_invent_reason_code(self):
        result = GenAIService(FakeProvider(model_output("INVENTED_SIGNAL"))).summarize(uuid4(), evidence())
        self.assertEqual(result["generation_mode"], "MODEL_FALLBACK")
        self.assertEqual(result["fallback_reason"], "invalid_model_output")
        self.assertNotIn("INVENTED_SIGNAL", json.dumps(result))

    def test_model_cannot_issue_a_decision(self):
        output = model_output()
        output["recommended_next_steps"] = ["Bloquear la cuenta."]
        result = GenAIService(FakeProvider(output)).summarize(uuid4(), evidence())
        self.assertTrue(result["fallback_used"])
        self.assertNotIn("Bloquear", json.dumps(result))

    def test_provider_failure_returns_fallback_without_mutating_case(self):
        case = evidence()
        original = copy.deepcopy(case)
        result = GenAIService(FakeProvider(error=TimeoutError())).summarize(uuid4(), case)
        self.assertEqual(case, original)
        self.assertEqual(result["transaction_id"], case["transaction_id"])
        self.assertEqual(result["generation_mode"], "MODEL_FALLBACK")
        self.assertEqual(result["fallback_reason"], "provider_error")

    def test_valid_provider_output_is_model_assisted(self):
        result = GenAIService(FakeProvider(model_output())).summarize(uuid4(), evidence())
        self.assertEqual(result["generation_mode"], "MODEL_ASSISTED")
        self.assertFalse(result["fallback_used"])
        validate("genai_summary", result)


if __name__ == "__main__":
    unittest.main()
