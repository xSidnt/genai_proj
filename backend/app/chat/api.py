import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from app.chat.models import ChatRequest, ChatResponse
from app.transcription.repository import TranscriptionRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
load_dotenv(BASE_DIR / ".env")


def _compact_notes(notes: list[dict]) -> list[dict]:
    return [
        {
            "pitch": note.get("pitch"),
            "midi": note.get("midi"),
            "string": note.get("string"),
            "fret": note.get("fret"),
            "start_seconds": note.get("start_seconds"),
            "duration_seconds": note.get("duration_seconds"),
            "confidence": note.get("confidence"),
            "finger": note.get("finger", "unknown"),
            "possible_technique": note.get("technique"),
            "technique_target_fret": note.get("technique_target_fret"),
            "bend_semitones": note.get("bend_semitones"),
        }
        for note in notes
    ]


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    repository = TranscriptionRepository(DATABASE_PATH)
    media = repository.get_upload_media(request.job_id)
    if not media:
        raise HTTPException(status_code=404, detail="Upload job was not found")

    duration = media[2]
    end = round(duration if request.end_seconds is None else min(duration, request.end_seconds), 3)
    start = round(min(duration, request.start_seconds), 3)
    transcription = repository.get(request.job_id, start, end)

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcribe the selected range before asking questions")

    visible_notes = [
        note for note in transcription["notes"]
        if start <= float(note.get("start_seconds", 0)) <= end
    ]
    context = {
        "job_id": request.job_id,
        "range": {"start_seconds": start, "end_seconds": end},
        "tuning": transcription["tuning"],
        "tempo_bpm": transcription["tempo_bpm"],
        "audio_source": transcription["audio_source"],
        "notes": _compact_notes(visible_notes),
    }

    provider = os.getenv("CHAT_PROVIDER", "openai").strip().lower()
    if provider == "gemini":
        return _chat_gemini(request.message, context)
    if provider == "openai":
        return _chat_openai(request.message, context)

    raise HTTPException(status_code=503, detail="No chat provider is configured")


def _chat_openai(message: str, context: dict) -> ChatResponse:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-6-luna")
        system = (
            "You are a guitar-practice assistant for the CroissantDough application. "
            "Answer using only the supplied transcription data. Do not invent notes, "
            "timings, chords, or technique that are absent. If evidence is uncertain, "
            "say it is uncertain and explain what is known. Technique hints are estimates. "
            "Keep answers practical and concise."
        )
        response = client.responses.create(
            model=model,
            text={"format": {"type": "text"}},
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Transcription context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {message}"},
            ],
        )
        reply = getattr(response, "output_text", "").strip()
        if not reply:
            raise RuntimeError("OpenAI returned an empty response")
        return ChatResponse(reply=reply, provider="openai")
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("OpenAI chat failed")
        raise HTTPException(status_code=502, detail=f"OpenAI chat failed: {error}") from error


def _chat_gemini(message: str, context: dict) -> ChatResponse:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_CHAT_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
        system = (
            "You are a guitar-practice assistant. Use only the supplied transcription data. "
            "Do not invent notes, timings, chords, or technique. Technique hints are estimates. Mark uncertainty clearly."
        )
        response = client.models.generate_content(
            model=model,
            contents=f"{system}\n\nTranscription context:\n{json.dumps(context, ensure_ascii=False)}\n\nQuestion: {message}",
        )
        reply = getattr(response, "text", "").strip()
        if not reply:
            raise RuntimeError("Gemini returned an empty response")
        return ChatResponse(reply=reply, provider="gemini")
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Gemini chat failed")
        raise HTTPException(status_code=502, detail=f"Gemini chat failed: {error}") from error
