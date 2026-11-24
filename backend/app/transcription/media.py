import subprocess
from pathlib import Path


class MediaTrimError(RuntimeError):
    pass


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
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError as error:
        raise MediaTrimError("ffmpeg is not installed") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "Unable to trim analysis audio"
        raise MediaTrimError(detail) from error
