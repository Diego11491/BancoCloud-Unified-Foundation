import os
import unittest
from unittest.mock import patch

from bancocloud.api.cors import DEFAULT_ALLOWED_ORIGINS, allowed_origins, parse_allowed_origins


class CorsConfigurationTests(unittest.TestCase):
    def test_defaults_are_loopback_only(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(allowed_origins(), list(DEFAULT_ALLOWED_ORIGINS))

    def test_configured_origins_are_trimmed_normalized_and_deduplicated(self):
        raw = " http://localhost:8081/,https://demo.example, http://localhost:8081 "
        self.assertEqual(
            parse_allowed_origins(raw),
            ["http://localhost:8081", "https://demo.example"],
        )

    def test_explicit_empty_value_disables_cross_origin_requests(self):
        with patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": ""}):
            self.assertEqual(allowed_origins(), [])

    def test_wildcard_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "wildcard"):
            parse_allowed_origins("*")

    def test_origin_with_path_or_unsupported_scheme_is_rejected(self):
        for value in ("http://localhost:8081/app", "file://local-app"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Invalid"):
                parse_allowed_origins(value)


if __name__ == "__main__":
    unittest.main()
