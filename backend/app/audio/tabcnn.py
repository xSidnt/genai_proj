from functools import lru_cache
from pathlib import Path

import librosa
import numpy as np
import onnxruntime as ort

from app.audio.notes import TranscriptionError, TranscriptionService


SAMPLE_RATE = 22050
HOP_LENGTH = 512
FRAME_SECONDS = HOP_LENGTH / SAMPLE_RATE


@lru_cache(maxsize=1)
def _load_model(model_path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    return ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])


def transcribe_tabcnn(audio_path: Path, model_path: Path) -> list[dict]:
    if not model_path.is_file():
        raise TranscriptionError("The local Electric Guitar model file is missing")

    try:
        audio, _ = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
        magnitude = np.abs(librosa.cqt(audio, sr=SAMPLE_RATE, hop_length=HOP_LENGTH, n_bins=192, bins_per_octave=24))
        levels = librosa.amplitude_to_db(magnitude, ref=np.max)
        features = (levels - levels.min()) / max(float(np.ptp(levels)), 1e-9)
        padded = np.pad(features, ((0, 0), (4, 4)))
        windows = np.lib.stride_tricks.sliding_window_view(padded, 9, axis=1)
        windows = np.ascontiguousarray(windows.transpose(1, 0, 2)[..., None], dtype=np.float32)
        model = _load_model(model_path)
        probabilities = np.exp(model.run(["output"], {"input": windows})[0])
    except Exception as error:
        raise TranscriptionError("Electric Guitar model could not process the audio") from error

    return _decode_notes(probabilities, len(audio) / SAMPLE_RATE)


def _decode_notes(probabilities: np.ndarray, duration: float) -> list[dict]:
    notes = []
    for column, (string, open_pitch) in enumerate(TranscriptionService.STANDARD_TUNING.items()):
        string_probs = probabilities[:, column]
        classes = string_probs.argmax(axis=1)
        # Remove a one-frame glitch when the surrounding positions agree.
        classes[1:-1] = np.where(classes[:-2] == classes[2:], classes[:-2], classes[1:-1])
        boundaries = np.r_[0, np.flatnonzero(np.diff(classes)) + 1, len(classes)]
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            position = int(classes[start])
            if position == 0 or end - start < 3:
                continue

            fret = position - 1
            midi = open_pitch + fret
            start_seconds = float(start * FRAME_SECONDS)
            end_seconds = min(float(end * FRAME_SECONDS), duration)
            if end_seconds <= start_seconds:
                continue
            notes.append({
                "pitch": TranscriptionService.midi_to_pitch(midi),
                "midi": midi,
                "string": string,
                "fret": fret,
                "start_seconds": round(start_seconds, 3),
                "duration_seconds": round(end_seconds - start_seconds, 3),
                "confidence": round(float(string_probs[start:end, position].mean()), 3),
            })

    return sorted(notes, key=lambda note: note["start_seconds"])
