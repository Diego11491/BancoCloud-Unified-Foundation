from pydantic import BaseModel, Field

class OnboardingRequest(BaseModel):
    region: str = Field(min_length=2, max_length=50)
