"""Evidence-only GenAI assistance for an already-created fraud case.

This module is deliberately outside scoring and case creation. A provider failure
always produces a deterministic local summary instead of propagating the failure.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen
from uuid import UUID

from bancocloud.contracts import validate

PROMPT_VERSION = "fraud-case-summary-v1"
LOCAL_MODEL = "deterministic-template-v1"

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CARD = re.compile(r"(?<![A-Z0-9])(?:\d[ -]?){13,19}(?![A-Z0-9])", re.IGNORECASE)
_SECRET_LABEL = re.compile(r"\b(?:cvv|cvc|pin|password|contrase(?:n|ñ)a)\b", re.IGNORECASE)
_PROHIBITED_DECISION = re.compile(
    r"\b(?:approve|approved|reject|rejected|block|blocked|freeze|cancel|"
    r"aprobar|aprobada|rechazar|rechazada|bloquear|bloqueada|congelar|"
    r"culpable|fraude confirmado)\b",
    re.IGNORECASE,
)
_MODEL_KEYS = {
    "summary", "signal_explanations", "missing_information",
    "recommended_next_steps", "limitations",
}


class GenAIProvider(Protocol):
    name: str
    model: str

    def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass
class HttpJsonProvider:
    """Small OpenAI-compatible adapter; endpoint must be the complete HTTPS URL."""

    endpoint: str
    api_key: str
    model: str
    name: str = "openai-compatible"
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    timeout_seconds: float = 15.0

    def generate(self, prompt: str) -> dict[str, Any]:
        if not self.endpoint.startswith("https://"):
            raise ValueError("GENAI_ENDPOINT must use HTTPS")
        payload = json.dumps({
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8")
        auth_value = f"{self.auth_scheme} {self.api_key}".strip()
        request = Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", self.auth_header: auth_value},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - HTTPS enforced
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return json.loads(content) if isinstance(content, str) else content


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "genai" / "fraud-case-summary.v1.md"
SYSTEM_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")


class GenAIService:
    def __init__(self, provider: GenAIProvider | None = None):
        self.provider = provider

    @classmethod
    def from_environment(cls) -> "GenAIService":
        endpoint = os.environ.get("GENAI_ENDPOINT", "").strip()
        if not endpoint:
            return cls()
        api_key = os.environ.get("GENAI_API_KEY", "")
        model = os.environ.get("GENAI_MODEL", "").strip()
        if not api_key or not model:
            raise ValueError("GENAI_API_KEY and GENAI_MODEL are required when GENAI_ENDPOINT is set")
        return cls(HttpJsonProvider(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            name=os.environ.get("GENAI_PROVIDER", "azure-openai"),
            auth_header=os.environ.get("GENAI_AUTH_HEADER", "api-key"),
            auth_scheme=os.environ.get("GENAI_AUTH_SCHEME", ""),
            timeout_seconds=float(os.environ.get("GENAI_TIMEOUT_SECONDS", "15")),
        ))

    def summarize(self, case_id: str | UUID, evidence: dict[str, Any]) -> dict[str, Any]:
        case_uuid = str(UUID(str(case_id)))
        validate("case", evidence)
        _reject_sensitive(evidence)
        reference = "sha256:" + hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()

        provider = self.provider
        content: dict[str, Any]
        mode = "LOCAL_DETERMINISTIC"
        fallback_used = False
        fallback_reason = None
        provider_name = "local"
        model = LOCAL_MODEL

        if provider is None:
            content = _local_content(evidence)
        else:
            provider_name, model = provider.name, provider.model
            try:
                generated = provider.generate(_build_prompt(case_uuid, evidence, reference))
            except Exception:  # Provider availability must never enter the critical path.
                content = _local_content(evidence)
                mode, fallback_used, fallback_reason = "MODEL_FALLBACK", True, "provider_error"
            else:
                try:
                    content = _validated_model_content(generated, evidence)
                    mode = "MODEL_ASSISTED"
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    content = _local_content(evidence)
                    mode, fallback_used, fallback_reason = "MODEL_FALLBACK", True, "invalid_model_output"

        result = {
            "schema_version": "1.0",
            "case_id": case_uuid,
            "transaction_id": evidence["transaction_id"],
            "correlation_id": evidence["correlation_id"],
            "input_reference": reference,
            "prompt_version": PROMPT_VERSION,
            "provider": provider_name,
            "model": model,
            "generation_mode": mode,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **content,
            "human_review_required": True,
            "decision_authority": "HUMAN_ANALYST",
        }
        _reject_sensitive(result)
        validate("genai_summary", result)
        return result


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _build_prompt(case_id: str, evidence: dict[str, Any], reference: str) -> str:
    envelope = {
        "prompt_version": PROMPT_VERSION,
        "case_id": case_id,
        "input_reference": reference,
        "evidence": evidence,
    }
    return SYSTEM_INSTRUCTIONS + "\nINPUT_JSON:\n" + _canonical(envelope)


def _local_content(evidence: dict[str, Any]) -> dict[str, Any]:
    codes = evidence["reason_codes"]
    signals = [{
        "code": code,
        "explanation": f"La política versionada registró la señal {code}; debe revisarse con la evidencia disponible.",
    } for code in codes]
    signal_text = ", ".join(codes) if codes else "sin reason codes registrados"
    return {
        "summary": (
            f"Caso HIGH con score {evidence['risk_score']:.3f}. Señales registradas: {signal_text}. "
            "Este resumen organiza evidencia y no constituye una decisión."
        ),
        "signal_explanations": signals,
        "missing_information": [
            "Confirmación del cliente no incluida en la evidencia estructurada.",
            "Resultado de la revisión humana todavía no registrado.",
        ],
        "recommended_next_steps": [
            "Revisar la transacción y sus reason codes en las fuentes gobernadas.",
            "Documentar la decisión y justificación del analista en el contrato correspondiente.",
        ],
        "limitations": [
            "Asistencia informativa basada únicamente en la evidencia recibida.",
            "No modifica el score, el caso ni el estado de la transacción.",
        ],
    }


def _validated_model_content(value: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _MODEL_KEYS:
        raise ValueError("Unexpected model output fields")
    for key in ("summary",):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"Invalid {key}")
    for key in ("signal_explanations", "missing_information", "recommended_next_steps", "limitations"):
        if not isinstance(value[key], list):
            raise ValueError(f"Invalid {key}")
    allowed_codes = set(evidence["reason_codes"])
    for signal in value["signal_explanations"]:
        if not isinstance(signal, dict) or set(signal) != {"code", "explanation"}:
            raise ValueError("Invalid signal explanation")
        if signal["code"] not in allowed_codes or not isinstance(signal["explanation"], str):
            raise ValueError("Model introduced an unsupported signal")
    if any(not isinstance(item, str) or not item.strip()
           for key in ("missing_information", "recommended_next_steps", "limitations")
           for item in value[key]):
        raise ValueError("Invalid model list item")
    text = _canonical(value)
    _reject_sensitive(value)
    if _PROHIBITED_DECISION.search(text):
        raise ValueError("Model attempted a prohibited decision")
    return value


def _reject_sensitive(value: Any) -> None:
    text = _canonical(value)
    if _EMAIL.search(text) or _CARD.search(text) or _SECRET_LABEL.search(text):
        raise ValueError("Sensitive or direct personal data is not accepted by GenAI")
