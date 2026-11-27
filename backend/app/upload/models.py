from pydantic import BaseModel


class VideoUploadResult(BaseModel):
    job_id: str
    status: str
    duration_seconds: float
    width: int | None
    height: int | None
    frame_rate: float | None
    video_path: str
    audio_path: str
