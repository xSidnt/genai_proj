import subprocess
from pathlib import Path


class AudioMediaError(RuntimeError):
    pass


def extract_wav(video_path: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-v", "error", "-i", str(video_path),
        "-vn", "-ac", "2", "-ar", "44100",
        "-acodec", "pcm_s16le", str(output),
    ]
    _run_ffmpeg(command, "Unable to extract audio")


def trim_audio(source: Path, output: Path, start_seconds: float, end_seconds: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end_seconds - start_seconds)
    command = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start_seconds:.3f}",
        "-i", str(source),
        "-t", f"{duration:.3f}",
        "-ac", "2", "-ar", "44100", "-acodec", "pcm_s16le",
        str(output),
    ]
    _run_ffmpeg(command, "Unable to trim analysis audio")


def _run_ffmpeg(command: list[str], fallback_message: str) -> None:
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError as error:
        raise AudioMediaError("ffmpeg is not installed") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or fallback_message
        raise AudioMediaError(detail) from error
