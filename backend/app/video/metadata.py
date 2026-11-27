import json
import subprocess
from pathlib import Path


class VideoMetadataError(RuntimeError):
    pass


def probe_video(video_path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "format=duration:stream=width,height,r_frame_rate,avg_frame_rate",
        "-of", "json", str(video_path),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except FileNotFoundError as error:
        raise VideoMetadataError("ffprobe is not installed") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "Unable to read video metadata"
        raise VideoMetadataError(detail) from error

    duration = float(data.get("format", {}).get("duration", 0))
    stream = (data.get("streams") or [{}])[0]
    frame_rate = _parse_fraction(stream.get("avg_frame_rate"))
    if not frame_rate:
        frame_rate = _parse_fraction(stream.get("r_frame_rate"))

    return {
        "duration_seconds": duration,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "frame_rate": frame_rate,
    }


def _parse_fraction(value: str | None) -> float | None:
    if not value:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None
