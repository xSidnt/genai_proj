from pydantic import BaseModel


class TabNote(BaseModel):
    pitch: str
    midi: int
    string: int
    fret: int
    start_seconds: float
    duration_seconds: float
    confidence: float


class TranscriptionResult(BaseModel):
    job_id: str
    status: str
    tuning: list[str]
    tempo_bpm: int | None
    notes: list[TabNote]
    audio_source: str
