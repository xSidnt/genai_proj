import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query

from app.audio.fingering import optimize_fingering
from app.audio.lead import select_lead_notes
from app.audio.media import AudioMediaError, trim_audio
from app.audio.notes import TranscriptionError, TranscriptionService
from app.audio.separation import GuitarSeparationService
from app.audio.tabcnn import transcribe_tabcnn
from app.audio.techniques import add_attack_and_bend_evidence, annotate_techniques
from app.audio.tempo import TempoDetectionError, detect_tempo
from app.transcription.models import TranscriptionResult
from app.transcription.repository import TranscriptionRepository
from app.video.fretboard import FretboardCalibration
from app.video.vision import GuitarVisionService

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transcriptions", tags=["transcriptions"])

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]
AUDIO_DIR = BASE_DIR / "storage" / "audio"
HAND_MODEL_PATH = BASE_DIR / "storage" / "models" / "hand_landmarker.task"
TAB_MODEL_PATH = BASE_DIR / "storage" / "models" / "tabcnn-gpfx.onnx"


@router.post("/{job_id}", response_model=TranscriptionResult)
def transcribe_job(
    job_id: str,
    start_seconds: float = Query(default=0.0, ge=0.0),
    end_seconds: float | None = Query(default=None, ge=0.0),
    calibration: FretboardCalibration | None = None,
    transcriber: Literal["basic_pitch", "tabcnn"] = "basic_pitch",
    audio_input: Literal["original", "guitar_stem"] = "guitar_stem",
    note_mode: Literal["polyphonic", "lead"] = "polyphonic",
    grid_bpm: int | None = Query(default=None, ge=30, le=300),
    vision_mode: Literal["configured", "audio_only"] = "configured",
) -> TranscriptionResult:
    repository = TranscriptionRepository(DATABASE_PATH)
    media = repository.get_upload_media(job_id)
    if not media:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    original_audio_path = Path(media[0])
    video_path = Path(media[1])
    duration = media[2]
    if calibration is not None and calibration.reference_seconds is not None and calibration.reference_seconds > duration + 0.001:
        raise HTTPException(status_code=422, detail="The calibration frame is outside the uploaded video")
    analysis_end = duration if end_seconds is None else end_seconds
    start = round(max(0.0, start_seconds), 3)
    end = round(min(duration, analysis_end), 3)

    if start >= end:
        raise HTTPException(status_code=422, detail="Analysis range must have a positive duration")
    if end - start < 0.5:
        raise HTTPException(status_code=422, detail="Analysis range must be at least 0.5 seconds")

    trimmed_dir = AUDIO_DIR / job_id / "ranges" / f"{start:.3f}-{end:.3f}"
    uses_configured_vision = transcriber == "basic_pitch" and vision_mode == "configured"
    analysis_profile = f"{transcriber}:{audio_input}:2"
    if note_mode == "lead":
        analysis_profile += f":lead:{grid_bpm or 'auto'}"
    if transcriber == "basic_pitch" and not uses_configured_vision:
        analysis_profile += ":audio_only"
    existing = repository.get(job_id, start, end) if calibration is None else None
    provider = os.getenv("VISION_PROVIDER", "gemini").strip().lower()
    provider_enabled = (
        (provider == "gemini" and bool(os.getenv("GEMINI_API_KEY")))
        or (provider == "openai" and bool(os.getenv("OPENAI_API_KEY")))
        or provider in {"jev", "local", "off"}
    )
    if existing and existing["analysis_profile"] == analysis_profile:
        notes = existing["notes"]
        provider_field = {
            "gemini": "gemini_answer",
            "openai": "openai_answer",
            "jev": "jev_answer",
            "local": "jev_answer",
        }.get(provider)
        has_provider_metadata = bool(notes) and (
            provider == "off" or (
                provider_field is not None
                and all(provider_field in note for note in notes)
            )
        )
        if not uses_configured_vision or (provider_enabled and has_provider_metadata):
            return TranscriptionResult(
                job_id=job_id,
                start_seconds=start,
                end_seconds=end,
                **existing,
            )

    if calibration is None:
        trimmed_dir.mkdir(parents=True, exist_ok=True)
        notes, tempo_bpm, tempo_source, audio_source = _analyze_audio(original_audio_path, trimmed_dir, start, end, transcriber, audio_input)
    else:
        with TemporaryDirectory(prefix="riffroom-calibrated-") as directory:
            notes, tempo_bpm, tempo_source, audio_source = _analyze_audio(original_audio_path, Path(directory), start, end, transcriber, audio_input)

    if note_mode == "lead":
        notes = select_lead_notes(notes, grid_bpm or tempo_bpm or 120, start, end)
    if transcriber == "basic_pitch":
        notes = optimize_fingering(notes)

    vision_started_at = perf_counter()
    observations = []
    if uses_configured_vision or calibration is not None:
        notes, observations = GuitarVisionService(HAND_MODEL_PATH).analyze(
            video_path, start, end, notes, bpm=(grid_bpm or tempo_bpm) if calibration else tempo_bpm, calibration=calibration,
        )
    annotate_techniques(notes)
    vision_seconds = round(perf_counter() - vision_started_at, 3) if calibration is not None else None

    if calibration is None:
        repository.save(
            job_id=job_id,
            start_seconds=start,
            end_seconds=end,
            status="ready",
            tuning=STANDARD_TUNING,
            tempo_bpm=tempo_bpm,
            tempo_source=tempo_source,
            analysis_profile=analysis_profile,
            notes=notes,
            audio_source=audio_source,
            video_observations=observations,
        )

    return TranscriptionResult(
        job_id=job_id,
        status="ready",
        tuning=STANDARD_TUNING,
        tempo_bpm=tempo_bpm,
        tempo_source=tempo_source,
        analysis_profile=analysis_profile,
        notes=notes,
        audio_source=audio_source,
        start_seconds=start,
        end_seconds=end,
        video_observations=observations,
        vision_seconds=vision_seconds,
    )


def _analyze_audio(
    original_audio_path: Path, trimmed_dir: Path, start: float, end: float,
    transcriber: str, audio_input: str,
) -> tuple[list[dict], int | None, str, str]:
    audio_path, tempo_bpm, tempo_source, audio_source = _prepare_audio(
        original_audio_path, trimmed_dir, start, end, audio_input,
    )
    return _predict_notes(audio_path, transcriber, start), tempo_bpm, tempo_source, audio_source


def _prepare_audio(
    original_audio_path: Path, trimmed_dir: Path, start: float, end: float, audio_input: str,
) -> tuple[Path, int | None, str, str]:
    trimmed_audio_path = trimmed_dir / "audio.wav"

    try:
        trim_audio(original_audio_path, trimmed_audio_path, start, end)
    except AudioMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    audio_for_transcription = trimmed_audio_path
    audio_source = "original"
    if audio_input == "guitar_stem":
        try:
            audio_for_transcription = GuitarSeparationService().separate_guitar(trimmed_audio_path, trimmed_dir / "guitar.wav")
            audio_source = "demucs_guitar"
        except Exception:
            audio_source = "original_fallback"
            logger.exception("Demucs guitar separation failed for range %s-%s; using original range", start, end)

    tempo_bpm = _estimate_tempo(trimmed_audio_path)
    tempo_source = "original" if tempo_bpm is not None else "unavailable"
    if tempo_bpm is None and audio_source == "demucs_guitar":
        tempo_bpm = _estimate_tempo(audio_for_transcription)
        if tempo_bpm is not None:
            tempo_source = "guitar_stem"

    return audio_for_transcription, tempo_bpm, tempo_source, audio_source


def _predict_notes(audio_path: Path, transcriber: str, start: float) -> list[dict]:
    try:
        if transcriber == "tabcnn":
            notes = transcribe_tabcnn(audio_path, TAB_MODEL_PATH)
            try:
                attacks = TranscriptionService().transcribe(audio_path)
                notes = add_attack_and_bend_evidence(notes, attacks)
            except TranscriptionError:
                logger.exception("Electric Guitar analysis could not add Basic Pitch attack or bend evidence")
        else:
            notes = TranscriptionService().transcribe(audio_path)
    except TranscriptionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    for note in notes:
        note["start_seconds"] = round(float(note["start_seconds"]) + start, 3)

    return notes


def _estimate_tempo(audio_path: Path) -> int | None:
    try:
        return detect_tempo(audio_path)
    except TempoDetectionError:
        logger.exception("BPM detection failed for %s", audio_path)
        return None


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
