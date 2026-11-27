import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.audio.media import AudioMediaError, extract_wav
from app.upload.models import VideoUploadResult
from app.upload.repository import UploadRepository
from app.video.metadata import VideoMetadataError, probe_video

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
AUDIO_DIR = STORAGE_DIR / "audio"
DATABASE_PATH = BASE_DIR / "data" / "videos.sqlite3"
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm"}
MAX_DURATION_SECONDS = 60
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


@router.post("", response_model=VideoUploadResult)
async def upload_video(file: UploadFile = File(...)) -> VideoUploadResult:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use MP4, MOV, or WebM.")

    job_id = str(uuid.uuid4())
    job_upload_dir = UPLOAD_DIR / job_id
    job_audio_dir = AUDIO_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_audio_dir.mkdir(parents=True, exist_ok=True)

    video_path = job_upload_dir / f"source{suffix}"
    audio_path = job_audio_dir / "audio.wav"

    size = 0
    with video_path.open("wb") as destination:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE_BYTES:
                video_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Video exceeds 100 MB")
            destination.write(chunk)

    try:
        metadata = probe_video(video_path)
        duration = metadata["duration_seconds"]

        if duration <= 0:
            raise HTTPException(status_code=422, detail="Could not determine video duration")
        if duration > MAX_DURATION_SECONDS:
            video_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Video must be 60 seconds or less")

        extract_wav(video_path, audio_path)
    except (AudioMediaError, VideoMetadataError) as error:
        video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error

    repository = UploadRepository(DATABASE_PATH)
    repository.create(
        job_id=job_id,
        original_name=file.filename or "video",
        video_path=str(video_path),
        audio_path=str(audio_path),
        duration_seconds=duration,
        width=metadata["width"],
        height=metadata["height"],
        frame_rate=metadata["frame_rate"],
    )

    return VideoUploadResult(
        job_id=job_id,
        status="ready",
        duration_seconds=duration,
        width=metadata["width"],
        height=metadata["height"],
        frame_rate=metadata["frame_rate"],
        video_path=str(video_path),
        audio_path=str(audio_path),
    )
