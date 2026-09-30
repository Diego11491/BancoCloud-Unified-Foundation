import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BICEP = ROOT / "infra" / "azure" / "bicep"


class AzureCostControlledSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (BICEP / "main-lite.bicep").read_text(encoding="utf-8")
        cls.foundation = (BICEP / "foundation-lite.bicep").read_text(
            encoding="utf-8"
        )
        cls.messaging = (BICEP / "messaging-lite.bicep").read_text(
            encoding="utf-8"
        )
        cls.preflight = (
            ROOT / "scripts" / "azure_cost_slice_preflight.ps1"
        ).read_text(encoding="utf-8")

    def test_expensive_capabilities_default_to_disabled(self):
        for parameter in (
            "deploySql",
            "deployServiceBus",
            "deployObservability",
            "deployContainerRegistry",
            "deployKeyVault",
        ):
            self.assertIn(f"param {parameter} bool = false", self.main)

        self.assertIn("param deployEventStreaming bool = true", self.main)
        self.assertIn("param deployDataLake bool = true", self.main)

    def test_sql_module_and_credentials_are_optional_together(self):
        self.assertIn("module data './data-lite.bicep' = if (deploySql)", self.main)
        self.assertIn("param sqlAdministratorLogin string = ''", self.main)
        self.assertIn("param sqlAdministratorPassword string = ''", self.main)
        self.assertNotIn("assert ", self.main)

    def test_foundation_cost_resources_are_conditional(self):
        expected_conditions = (
            "if (deployObservability)",
            "if (deployContainerRegistry)",
            "if (deployKeyVault)",
        )
        for condition in expected_conditions:
            self.assertIn(condition, self.foundation)

        self.assertIn("resource workloadIdentity", self.foundation)
        self.assertNotIn(
            "resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if",
            self.foundation,
        )

    def test_messaging_and_lake_resources_are_guarded(self):
        self.assertIn("if (deployEventStreaming)", self.messaging)
        self.assertIn("if (deployDataLake)", self.messaging)
        self.assertIn("if (deployServiceBus)", self.messaging)
        self.assertIn(
            "var effectiveDeployDataLake = deployDataLake || deployEventStreaming",
            self.main,
        )
        self.assertIn("deployDataLake: effectiveDeployDataLake", self.main)
        self.assertNotIn("assert ", self.messaging)

    def test_preflight_cannot_deploy_and_checks_forbidden_families(self):
        normalized = " ".join(self.preflight.lower().split())
        self.assertNotIn("deployment group create", normalized)
        self.assertIn("deployment', 'group', 'validate'", self.preflight)
        self.assertIn("deployment', 'group', 'what-if'", self.preflight)
        self.assertIn(
            "if ($effectiveRoles -notcontains 'Owner')",
            self.preflight,
        )
        self.assertIn("The preflight requires an empty dedicated Resource Group", self.preflight)

        for family in (
            "Microsoft.Sql",
            "Microsoft.ServiceBus",
            "Microsoft.ContainerRegistry",
            "Microsoft.OperationalInsights",
            "Microsoft.Insights",
            "Microsoft.KeyVault",
        ):
            self.assertIn(family, self.preflight)


if __name__ == "__main__":
    unittest.main()
