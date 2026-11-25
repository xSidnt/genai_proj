from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    job_id: str
    message: str = Field(min_length=1, max_length=2000)
    start_seconds: float = 0.0
    end_seconds: float | None = None


class ChatResponse(BaseModel):
    reply: str
    provider: str
