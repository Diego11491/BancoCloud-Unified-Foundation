import json
import os
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from src.aws.bff.auth.claims import Unauthorized, claims


ISSUER = "https://trusted.issuer.example"
AUDIENCE = "trusted-client"
CUSTOMER_REF = "007796d7-43a4-50c7-8093-1a7caf001771"


class BffAuthConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = json.loads(RSAAlgorithm.to_jwk(cls.private_key.public_key()))
        cls.jwk["kid"] = "test-key"

    def event(self, *, issuer=ISSUER, audience=AUDIENCE):
        token = jwt.encode(
            {
                "iss": issuer,
                "aud": audience,
                "exp": int(time.time()) + 300,
                "sub": "test-subject",
                "token_use": "id",
                "custom:customer_ref": CUSTOMER_REF,
            },
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )
        return {"headers": {"Authorization": f"Bearer {token}"}}

    def assert_missing_configuration(self, name, value=None):
        config = {"COGNITO_ISSUER": ISSUER, "COGNITO_AUDIENCE": AUDIENCE}
        if value is None:
            del config[name]
        else:
            config[name] = value
        with patch.dict(os.environ, config, clear=True), patch(
            "src.aws.bff.auth.claims.get_jwks"
        ) as get_jwks:
            with self.assertRaisesRegex(Unauthorized, "MISSING_CONFIGURATION"):
                claims(self.event())
            get_jwks.assert_not_called()

    def test_missing_issuer_fails_closed(self):
        self.assert_missing_configuration("COGNITO_ISSUER")

    def test_blank_issuer_fails_closed(self):
        self.assert_missing_configuration("COGNITO_ISSUER", "")

    def test_whitespace_issuer_fails_closed(self):
        self.assert_missing_configuration("COGNITO_ISSUER", "   ")

    def test_missing_audience_fails_closed(self):
        self.assert_missing_configuration("COGNITO_AUDIENCE")

    def test_blank_audience_fails_closed(self):
        self.assert_missing_configuration("COGNITO_AUDIENCE", "")

    def test_whitespace_audience_fails_closed(self):
        self.assert_missing_configuration("COGNITO_AUDIENCE", "   ")

    def test_valid_configuration_uses_one_verified_decode(self):
        real_decode = jwt.decode
        with patch.dict(os.environ, {"COGNITO_ISSUER": ISSUER, "COGNITO_AUDIENCE": AUDIENCE}, clear=True), patch(
            "src.aws.bff.auth.claims.get_jwks", return_value={"keys": [self.jwk]}
        ) as get_jwks, patch("src.aws.bff.auth.claims.jwt.decode", wraps=real_decode) as decode:
            result = claims(self.event())
        self.assertEqual(result["custom:customer_ref"], CUSTOMER_REF)
        get_jwks.assert_called_once_with(ISSUER)
        decode.assert_called_once()
        self.assertEqual(decode.call_args.kwargs["issuer"], ISSUER)
        self.assertEqual(decode.call_args.kwargs["audience"], AUDIENCE)
        self.assertEqual(decode.call_args.kwargs["algorithms"], ["RS256"])

    def test_unverified_issuer_cannot_choose_jwks_source(self):
        with patch.dict(os.environ, {"COGNITO_ISSUER": ISSUER, "COGNITO_AUDIENCE": AUDIENCE}, clear=True), patch(
            "src.aws.bff.auth.claims.get_jwks", return_value={"keys": [self.jwk]}
        ) as get_jwks:
            with self.assertRaisesRegex(Unauthorized, "WRONG_ISSUER"):
                claims(self.event(issuer="https://attacker.example"))
        get_jwks.assert_called_once_with(ISSUER)

    def test_wrong_issuer_rejected(self):
        with patch.dict(os.environ, {"COGNITO_ISSUER": ISSUER, "COGNITO_AUDIENCE": AUDIENCE}, clear=True), patch(
            "src.aws.bff.auth.claims.get_jwks", return_value={"keys": [self.jwk]}
        ):
            with self.assertRaisesRegex(Unauthorized, "WRONG_ISSUER"):
                claims(self.event(issuer="https://wrong.issuer.example"))

    def test_wrong_audience_rejected(self):
        with patch.dict(os.environ, {"COGNITO_ISSUER": ISSUER, "COGNITO_AUDIENCE": AUDIENCE}, clear=True), patch(
            "src.aws.bff.auth.claims.get_jwks", return_value={"keys": [self.jwk]}
        ):
            with self.assertRaisesRegex(Unauthorized, "WRONG_AUDIENCE"):
                claims(self.event(audience="wrong-client"))


if __name__ == "__main__":
    unittest.main()
