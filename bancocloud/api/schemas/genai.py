from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CaseSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    evidence: dict[str, Any]
