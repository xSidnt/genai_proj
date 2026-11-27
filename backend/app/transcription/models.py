from pydantic import BaseModel


class TabNote(BaseModel):
    pitch: str
    midi: int
    string: int
    fret: int
    start_seconds: float
    grid_seconds: float | None = None
    duration_seconds: float
    confidence: float
    technique: str | None = None
    technique_target_fret: int | None = None
    bend_semitones: float | None = None
    audio_string: int | None = None
    audio_fret: int | None = None
    visual_status: str | None = None
    visual_confidence: float | None = None
    combined_confidence: float | None = None
    visual_string: int | None = None
    visual_fret: int | None = None
    visual_index_fret: float | None = None
    visual_hand_fret: float | None = None
    finger: str = "unknown"
    gemini_answer: dict | None = None
    jev_answer: str | None = None
    jev_probabilities: dict[str, float] = {}
    answer_mass: float = 0.0
    openai_answer: dict | None = None


class VideoObservation(BaseModel):
    timestamp_seconds: float
    hands_visible: int
    fretting_hand_visible: bool
    neck_visible: bool
    visual_confidence: float
    measure_anchor: bool = False
    fretboard_reanchored: bool = False


class TranscriptionResult(BaseModel):
    job_id: str
    status: str
    tuning: list[str]
    tempo_bpm: int | None
    tempo_source: str | None = None
    analysis_profile: str | None = None
    notes: list[TabNote]
    audio_source: str
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    video_observations: list[VideoObservation] = []
    vision_seconds: float | None = None
