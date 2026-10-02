import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from src.aws.bff.middleware.errors import handle_error

class TestBffErrorPropagation(unittest.TestCase):
    def test_http_error_propagation(self):
        codes = [401, 403, 404, 500]
        for code in codes:
            with self.subTest(code=code):
                fp = MagicMock()
                fp.read.return_value = b'{"detail": "error"}'
                exc = HTTPError("http://url", code, "Error", hdrs={}, fp=fp)
                res = handle_error(exc, "corr-1")
                self.assertEqual(res["statusCode"], code)
                self.assertIn("error", res["body"])

if __name__ == "__main__":
    unittest.main()
