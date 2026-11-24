from pathlib import Path

import librosa
import numpy as np


class TempoDetectionError(RuntimeError):
    pass


def detect_tempo(audio_path: Path) -> int | None:
    if not audio_path.exists():
        raise TempoDetectionError("Audio file was not found")

    try:
        y, sample_rate = librosa.load(str(audio_path), sr=22050, mono=True)
        if y.size < sample_rate:
            return None

        tempo, beats = librosa.beat.beat_track(y=y, sr=sample_rate, units="time")
        tempo_value = float(np.asarray(tempo).reshape(-1)[0])

        if not np.isfinite(tempo_value) or tempo_value <= 0:
            return None

        while tempo_value < 60:
            tempo_value *= 2
        while tempo_value > 300:
            tempo_value /= 2

        return round(max(30, min(300, tempo_value)))
    except Exception as error:
        raise TempoDetectionError("Could not estimate tempo") from error
