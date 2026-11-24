from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.transcription.models import TranscriptionResult
from app.transcription.repository import TranscriptionRepository
from app.transcription.service import TranscriptionError, TranscriptionService

router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]
# only works for standard tuining?

@router.post("/{job_id}", response_model=TranscriptionResult)
def transcribe_job(job_id: str) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    existing = repository.get(job_id)
    if existing:
        return TranscriptionResult(job_id=job_id, **existing)

    audio_path_text = repository.get_upload_audio_path(job_id)
    if not audio_path_text:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    try:
        notes = TranscriptionService().transcribe(Path(audio_path_text))
    except TranscriptionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    repository.save(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=None,
        notes=notes,
    )

    return TranscriptionResult(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=None,
        notes=notes,
    )


@router.get("/{job_id}", response_model=TranscriptionResult)
def get_transcription(job_id: str) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    result = repository.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcription was not found")

    return TranscriptionResult(job_id=job_id, **result)
