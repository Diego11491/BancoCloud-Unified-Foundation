import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from bancocloud.application.genai_service import GenAIService
from scripts.smoke_genai_local import validate_summary


ROOT = Path(__file__).resolve().parents[3]


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
        "created_at": "2026-09-28T00:00:00Z",
    }


class GenAISmokeValidationTests(unittest.TestCase):
    def test_script_loads_when_invoked_by_path_outside_repository(self):
        script = ROOT / "scripts" / "smoke_genai_local.py"
        command = (
            "import runpy; "
            f"runpy.run_path({str(script)!r}, run_name='smoke_import_check')"
        )
        with tempfile.TemporaryDirectory() as outside_repository:
            result = subprocess.run(
                [sys.executable, "-c", command],
                cwd=outside_repository,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_valid_local_summary_preserves_case_and_correlation(self):
        case_id = str(uuid4())
        case = evidence()
        summary = GenAIService().summarize(case_id, case)
        validate_summary(summary, case_id, case)

    def test_mismatched_correlation_is_rejected(self):
        case_id = str(uuid4())
        case = evidence()
        summary = GenAIService().summarize(case_id, case)
        invalid = copy.deepcopy(summary)
        invalid["correlation_id"] = str(uuid4())
        with self.assertRaisesRegex(RuntimeError, "correlation"):
            validate_summary(invalid, case_id, case)


if __name__ == "__main__":
    unittest.main()
