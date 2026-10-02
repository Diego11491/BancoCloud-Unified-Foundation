import os
import pytest
from unittest.mock import patch, MagicMock

os.environ["COGNITO_ISSUER"] = "https://trusted.issuer.com"
os.environ["COGNITO_AUDIENCE"] = "trusted_aud"

from src.aws.bff.auth.claims import claims, Unauthorized

@patch("src.aws.bff.auth.claims.jwt")
@patch("src.aws.bff.auth.claims.get_jwks")
@patch("src.aws.bff.auth.claims.RSAAlgorithm.from_jwk")
def test_trusted_configured_issuer_determines_jwks_source(mock_from_jwk, mock_get_jwks, mock_jwt):
    mock_jwt.get_unverified_header.return_value = {"kid": "key1"}
    
    # Simulate an attacker trying to redirect JWKS by forging 'iss'
    mock_jwt.decode.side_effect = [{"iss": "https://attacker.com"}, {"token_use": "id", "custom:customer_ref": "007796d7-43a4-50c7-8093-1a7caf001771", "sub": "sub"}]
    mock_get_jwks.return_value = {"keys": [{"kid": "key1"}]}
    mock_from_jwk.return_value = "fake_rsa_key"

    event = {"headers": {"Authorization": "Bearer fake_token"}}
    
    # Test valid claim extraction
    result = claims(event)
    
    # Assert get_jwks was called with the TRUSTED issuer from environment, NOT the attacker's issuer
    mock_get_jwks.assert_called_once_with("https://trusted.issuer.com")
    
    # Assert jwt.decode was called with trusted issuer and audience
    calls = mock_jwt.decode.call_args_list
    assert calls[1][1]["issuer"] == "https://trusted.issuer.com"
    assert calls[1][1]["audience"] == "trusted_aud"

@patch("src.aws.bff.auth.claims.jwt")
@patch("src.aws.bff.auth.claims.get_jwks")
@patch("src.aws.bff.auth.claims.RSAAlgorithm.from_jwk")
def test_wrong_issuer(mock_from_jwk, mock_get_jwks, mock_jwt):
    mock_jwt.get_unverified_header.return_value = {"kid": "key1"}
    import jwt
    mock_jwt.InvalidIssuerError = jwt.InvalidIssuerError
    
    # Fail on second decode (signature validation)
    mock_jwt.decode.side_effect = [{"iss": "https://trusted.issuer.com"}, jwt.InvalidIssuerError()]
    mock_get_jwks.return_value = {"keys": [{"kid": "key1"}]}
    
    event = {"headers": {"Authorization": "Bearer fake_token"}}
    
    with pytest.raises(Unauthorized, match="WRONG_ISSUER"):
        claims(event)

# Add remaining tests as requested by the prompt
