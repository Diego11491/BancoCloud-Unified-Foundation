from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalystDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    case_id: UUID
    transaction_id: UUID
    decision: Literal["CONFIRMED_FRAUD", "LEGITIMATE", "INCONCLUSIVE"]
    decided_at: datetime
    analyst_ref: str = Field(min_length=8, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)
    correlation_id: UUID
