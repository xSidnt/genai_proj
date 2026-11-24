import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query

from app.transcription.media import MediaTrimError, trim_audio
from app.transcription.models import TranscriptionResult
from app.transcription.repository import TranscriptionRepository
from app.transcription.separation import GuitarSeparationService
from app.transcription.service import TranscriptionError, TranscriptionService
from app.transcription.tempo import TempoDetectionError, detect_tempo
from app.transcription.vision import GuitarVisionService

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]
AUDIO_DIR = BASE_DIR / "storage" / "audio"
HAND_MODEL_PATH = BASE_DIR / "storage" / "models" / "hand_landmarker.task"


@router.post("/{job_id}", response_model=TranscriptionResult)
def transcribe_job(
    job_id: str,
    start_seconds: float = Query(default=0.0, ge=0.0),
    end_seconds: float | None = Query(default=None, ge=0.0),
) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    media = repository.get_upload_media(job_id)
    if not media:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    original_audio_path = Path(media[0])
    video_path = Path(media[1])
    duration = media[2]
    analysis_end = duration if end_seconds is None else end_seconds
    start = round(max(0.0, start_seconds), 3)
    end = round(min(duration, analysis_end), 3)

    if start >= end:
        raise HTTPException(status_code=422, detail="Analysis range must have a positive duration")
    if end - start < 0.5:
        raise HTTPException(status_code=422, detail="Analysis range must be at least 0.5 seconds")

    existing = repository.get(job_id, start, end)
    gemini_enabled = bool(os.getenv("GEMINI_API_KEY"))
    jev_enabled = os.getenv("JEV_VISION_ENABLED", "true").lower() not in {"0", "false", "no"}
    if existing:
        notes = existing["notes"]
        has_vision_metadata = bool(notes) and all("gemini_answer" in note or "jev_answer" in note for note in notes)
        if (not gemini_enabled and not jev_enabled) or (gemini_enabled and has_vision_metadata) or (not gemini_enabled and jev_enabled and has_vision_metadata):
            return TranscriptionResult(
                job_id=job_id,
                start_seconds=start,
                end_seconds=end,
                **existing,
            )

    trimmed_dir = AUDIO_DIR / job_id / "ranges" / f"{start:.3f}-{end:.3f}"
    trimmed_dir.mkdir(parents=True, exist_ok=True)
    trimmed_audio_path = trimmed_dir / "audio.wav"

    try:
        trim_audio(original_audio_path, trimmed_audio_path, start, end)
    except MediaTrimError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    audio_for_transcription = trimmed_audio_path
    audio_source = "original_fallback"
    guitar_stem_path = trimmed_dir / "guitar.wav"

    try:
        audio_for_transcription = GuitarSeparationService().separate_guitar(
            trimmed_audio_path,
            guitar_stem_path,
        )
        audio_source = "demucs_guitar"
    except Exception:
        logger.exception("Demucs guitar separation failed for range %s-%s; using original range", start, end)

    try:
        notes = TranscriptionService().transcribe(audio_for_transcription)
    except TranscriptionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        tempo_bpm = detect_tempo(audio_for_transcription)
    except TempoDetectionError:
        logger.exception("BPM detection failed for range %s-%s", start, end)
        tempo_bpm = None

    for note in notes:
        note["start_seconds"] = round(float(note["start_seconds"]) + start, 3)

    notes, observations = GuitarVisionService(HAND_MODEL_PATH).analyze(
        video_path,
        start,
        end,
        notes,
        bpm=tempo_bpm,
    )

    repository.save(
        job_id=job_id,
        start_seconds=start,
        end_seconds=end,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=tempo_bpm,
        notes=notes,
        audio_source=audio_source,
        video_observations=observations,
    )

    return TranscriptionResult(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=tempo_bpm,
        notes=notes,
        audio_source=audio_source,
        start_seconds=start,
        end_seconds=end,
        video_observations=observations,
    )


@router.get("/{job_id}", response_model=TranscriptionResult)
def get_transcription(
    job_id: str,
    start_seconds: float = Query(default=0.0, ge=0.0),
    end_seconds: float | None = Query(default=None, ge=0.0),
) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    media = repository.get_upload_media(job_id)
    if not media:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    end = round(media[2] if end_seconds is None else min(media[2], end_seconds), 3)
    start = round(min(media[2], start_seconds), 3)
    result = repository.get(job_id, start, end)
    if not result:
        raise HTTPException(status_code=404, detail="Transcription was not found")

    return TranscriptionResult(job_id=job_id, start_seconds=start, end_seconds=end, **result)
