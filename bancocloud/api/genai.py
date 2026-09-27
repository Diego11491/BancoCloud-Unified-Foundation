from fastapi import Depends, FastAPI, HTTPException

from bancocloud.api.dependencies import require_demo_key
from bancocloud.api.schemas.genai import CaseSummaryRequest
from bancocloud.application.genai_service import GenAIService

app = FastAPI(title="BancoCloud GenAI Case Assistance LOCAL FIRST", docs_url=None, redoc_url=None)
_secure = [Depends(require_demo_key)]


@app.get("/health")
def health():
    return {"status": "ok", "critical_path": False}


@app.post("/explain-case", dependencies=_secure)
def explain_case(request: CaseSummaryRequest):
    try:
        return GenAIService.from_environment().summarize(request.case_id, request.evidence)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
