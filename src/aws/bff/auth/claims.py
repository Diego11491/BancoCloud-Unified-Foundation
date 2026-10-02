import os
import json
import uuid
import urllib.request
import jwt
from jwt.algorithms import RSAAlgorithm

class Unauthorized(ValueError): pass

JWKS_CACHE = {}

def get_jwks(issuer):
    if issuer in JWKS_CACHE:
        return JWKS_CACHE[issuer]
    jwks_url = f"{issuer}/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(jwks_url) as response:
            JWKS_CACHE[issuer] = json.loads(response.read().decode('utf-8'))
            return JWKS_CACHE[issuer]
    except Exception as e:
        print(f"Failed to fetch JWKS: {e}")
        return None

def claims(event: dict) -> dict:
    auth = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    if auth:
        if not auth.get("sub"):
            raise Unauthorized("JWT subject missing")
        return auth
    
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization") or headers.get("Authorization")
    
    print("AUTH_HEADER_PRESENT — " + ("YES" if auth_header else "NO"))
    if not auth_header:
        print("AUTH_RESULT — MISSING_BEARER")
        raise Unauthorized("MISSING_BEARER")
        
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        print("BEARER_PARSED — NO")
        print("AUTH_RESULT — MISSING_BEARER")
        raise Unauthorized("MISSING_BEARER")
        
    token = parts[1]
    print("BEARER_PARSED — YES")
    
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        print("JWT_KID_PRESENT — " + ("YES" if kid else "NO"))
        if not kid:
            raise Exception("UNKNOWN_KID")
            
        expected_issuer = os.environ.get("COGNITO_ISSUER", "").strip()
        if not expected_issuer:
            print("AUTH_RESULT — MISSING_CONFIGURATION")
            raise Unauthorized("MISSING_CONFIGURATION")
        expected_audience = os.environ.get("COGNITO_AUDIENCE", "").strip()
        if not expected_audience:
            print("AUTH_RESULT — MISSING_CONFIGURATION")
            raise Unauthorized("MISSING_CONFIGURATION")
            
        jwks = get_jwks(expected_issuer)
        if not jwks:
            print("JWKS_KEY_RESOLVED \u2014 NO")
            raise Exception("UNKNOWN_KID")
            
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = RSAAlgorithm.from_jwk(json.dumps(key))
                break
                
        print("JWKS_KEY_RESOLVED \u2014 " + ("YES" if rsa_key else "NO"))
        if not rsa_key:
            raise Exception("UNKNOWN_KID")
            
        try:
            decoded = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=expected_audience,
                issuer=expected_issuer,
                options={"verify_exp": True}
            )
            print("JWT_SIGNATURE_VERIFIED \u2014 YES")
        except jwt.ExpiredSignatureError:
            print("JWT_SIGNATURE_VERIFIED — YES")
            print("ISSUER_MATCH — YES")
            print("AUDIENCE_MATCH — YES")
            print("EXP_VALID — NO")
            print("AUTH_RESULT — EXPIRED")
            raise Unauthorized("EXPIRED")
        except jwt.InvalidIssuerError:
            print("JWT_SIGNATURE_VERIFIED — YES")
            print("ISSUER_MATCH — NO")
            print("AUTH_RESULT — WRONG_ISSUER")
            raise Unauthorized("WRONG_ISSUER")
        except jwt.InvalidAudienceError:
            print("JWT_SIGNATURE_VERIFIED — YES")
            print("ISSUER_MATCH — YES")
            print("AUDIENCE_MATCH — NO")
            print("AUTH_RESULT — WRONG_AUDIENCE")
            raise Unauthorized("WRONG_AUDIENCE")
        except jwt.InvalidSignatureError:
            print("JWT_SIGNATURE_VERIFIED — NO")
            print("AUTH_RESULT — INVALID_SIGNATURE")
            raise Unauthorized("INVALID_SIGNATURE")
        except Exception as e:
            print("JWT_SIGNATURE_VERIFIED — NO")
            print("AUTH_RESULT — INVALID_SIGNATURE")
            raise Unauthorized("INVALID_SIGNATURE")

        print("ISSUER_MATCH — YES")
        print("AUDIENCE_MATCH — YES")
        print("EXP_VALID — YES")
        
        token_use = decoded.get("token_use")
        print("TOKEN_USE — " + str(token_use))
        if token_use != "id":
            print("AUTH_RESULT — WRONG_TOKEN_USE")
            raise Unauthorized("WRONG_TOKEN_USE")
            
        sub = decoded.get("sub")
        print("SUB_PRESENT — " + ("YES" if sub else "NO"))
        
        customer_ref_val = decoded.get("custom:customer_ref") or decoded.get("customer_ref")
        print("CUSTOMER_REF_PRESENT — " + ("YES" if customer_ref_val else "NO"))
        
        if not customer_ref_val:
            print("AUTH_RESULT — MISSING_CUSTOMER_REF")
            raise Unauthorized("MISSING_CUSTOMER_REF")
            
        try:
            uuid.UUID(customer_ref_val)
            print("CUSTOMER_REF_UUID_VALID — YES")
        except:
            print("CUSTOMER_REF_UUID_VALID — NO")
            print("AUTH_RESULT — INVALID_CUSTOMER_REF")
            raise Unauthorized("INVALID_CUSTOMER_REF")
            
        print("AUTH_RESULT — SUCCESS")
        return decoded
        
    except Unauthorized:
        raise
    except Exception as e:
        print(f"AUTH_RESULT — {str(e)}")
        raise Unauthorized(str(e))

def customer_ref(event: dict) -> str:
    c = claims(event)
    value = c.get("custom:customer_ref") or c.get("customer_ref")
    if not value:
        raise Unauthorized("customer_ref claim missing")
    return value
