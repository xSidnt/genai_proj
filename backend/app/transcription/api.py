import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.transcription.models import TranscriptionResult
from app.transcription.repository import TranscriptionRepository
from app.transcription.separation import GuitarSeparationService
from app.transcription.service import TranscriptionError, TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]
AUDIO_DIR = BASE_DIR / "storage" / "audio"


@router.post("/{job_id}", response_model=TranscriptionResult)
def transcribe_job(job_id: str) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    existing = repository.get(job_id)
    if existing and existing["audio_source"] != "original":
        return TranscriptionResult(job_id=job_id, **existing)

    audio_path_text = repository.get_upload_audio_path(job_id)
    if not audio_path_text:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    original_audio_path = Path(audio_path_text)
    audio_for_transcription = original_audio_path
    audio_source = "original_fallback"
    guitar_stem_path = AUDIO_DIR / job_id / "guitar.wav"

    try:
        audio_for_transcription = GuitarSeparationService().separate_guitar(
            original_audio_path,
            guitar_stem_path,
        )
        audio_source = "demucs_guitar"
    except Exception:
        logger.exception("Demucs guitar separation failed for upload %s; using original audio", job_id)

    try:
        notes = TranscriptionService().transcribe(audio_for_transcription)
    except TranscriptionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    repository.save(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=None,
        notes=notes,
        audio_source=audio_source,
    )

    return TranscriptionResult(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=None,
        notes=notes,
        audio_source=audio_source,
    )


@router.get("/{job_id}", response_model=TranscriptionResult)
def get_transcription(job_id: str) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    result = repository.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transcription was not found")

    return TranscriptionResult(job_id=job_id, **result)
