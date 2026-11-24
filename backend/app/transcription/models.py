from pydantic import BaseModel


class TabNote(BaseModel):
    pitch: str
    midi: int
    string: int
    fret: int
    start_seconds: float
    duration_seconds: float
    confidence: float
    visual_status: str | None = None
    visual_confidence: float | None = None
    combined_confidence: float | None = None
    visual_string: int | None = None
    visual_fret: int | None = None
    finger: str = "unknown"
    gemini_answer: dict | None = None
    jev_answer: str | None = None
    jev_probabilities: dict[str, float] = {}
    answer_mass: float = 0.0


class VideoObservation(BaseModel):
    timestamp_seconds: float
    hands_visible: int
    fretting_hand_visible: bool
    neck_visible: bool
    visual_confidence: float


class TranscriptionResult(BaseModel):
    job_id: str
    status: str
    tuning: list[str]
    tempo_bpm: int | None
    notes: list[TabNote]
    audio_source: str
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    video_observations: list[VideoObservation] = []
