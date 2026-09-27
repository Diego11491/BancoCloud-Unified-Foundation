import json
from pathlib import Path

import re
from datetime import datetime
from uuid import UUID

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # Offline generation and contract tests use the same canonical schema.
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    "transaction": "transaction.v1.schema.json",
    "score": "fraud-score.v1.schema.json",
    "case": "create-fraud-case.v1.schema.json",
    "decision": "analyst-decision.v1.schema.json",
    "genai_summary": "genai-case-summary.v1.schema.json",
}


def validate(name, payload):
    schema = json.loads((ROOT / "contracts" / SCHEMAS[name]).read_text())
    if Draft202012Validator:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    else:
        _validate_subset(schema, payload)
    return payload


def _validate_subset(schema, value):
    """Offline verifier for the keywords actually used by the four v1 contracts."""
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    predicates = {"object":lambda v:isinstance(v,dict), "array":lambda v:isinstance(v,list),
                  "string":lambda v:isinstance(v,str), "number":lambda v:isinstance(v,(int,float)) and not isinstance(v,bool),
                  "integer":lambda v:isinstance(v,int) and not isinstance(v,bool),
                  "boolean":lambda v:isinstance(v,bool), "null":lambda v:v is None}
    if kinds and not any(predicates[k](value) for k in kinds):
        raise ValueError("Invalid schema type")
    if "const" in schema and value != schema["const"]:
        raise ValueError("Invalid schema constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Invalid schema enumeration")
    if isinstance(value, dict):
        fields = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            raise ValueError("Missing required schema field")
        if schema.get("additionalProperties") is False and any(k not in fields for k in value):
            raise ValueError("Unexpected schema field")
        for k,v in value.items():
            if k in fields: _validate_subset(fields[k], v)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError("Too few array elements")
        if len(value) > schema.get("maxItems", float("inf")):
            raise ValueError("Too many array elements")
        if schema.get("uniqueItems") and len({json.dumps(v,sort_keys=True) for v in value}) != len(value):
            raise ValueError("Duplicate array element")
        for v in value: _validate_subset(schema.get("items", {}),v)
    if isinstance(value, str):
        if len(value) < schema.get("minLength",0) or len(value) > schema.get("maxLength",float("inf")):
            raise ValueError("Invalid string length")
        if "pattern" in schema and not re.search(schema["pattern"],value):
            raise ValueError("Invalid string pattern")
        if schema.get("format") == "uuid": UUID(value)
        if schema.get("format") == "date-time":
            dt = datetime.fromisoformat(value.replace("Z","+00:00"))
            if dt.tzinfo is None: raise ValueError("Timezone required")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if "minimum" in schema and value < schema["minimum"]: raise ValueError("Below minimum")
        if "maximum" in schema and value > schema["maximum"]: raise ValueError("Above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]: raise ValueError("Below exclusive minimum")
