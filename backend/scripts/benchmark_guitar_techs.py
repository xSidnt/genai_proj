"""Score the Guitar-TECHS P3 amplifier-microphone recordings against per-string MIDI."""

import argparse
from collections import defaultdict
import io
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from time import perf_counter
from zipfile import ZipFile

import mido
import numpy as np
import soundfile

from app.audio.fingering import optimize_fingering
from app.audio.lead import select_lead_notes
from app.audio.notes import TranscriptionService
from app.audio.tabcnn import transcribe_tabcnn
from app.transcription.api import TAB_MODEL_PATH, _predict_notes, _prepare_audio
from scripts.benchmark_egset12 import score, show_result


def load_reference(data: bytes, duration: float) -> list[dict]:
    notes = []
    active = {}
    timestamp = 0
    for message in mido.MidiFile(file=io.BytesIO(data)):
        timestamp += message.time
        if message.type not in {"note_on", "note_off"}:
            continue
        string = message.channel + 1
        if string not in TranscriptionService.STANDARD_TUNING:
            continue
        midi = message.note
        key = string, midi
        start = active.pop(key, None)
        fret = midi - TranscriptionService.STANDARD_TUNING[string]
        if start is not None and 0 <= fret <= 24 and start < min(timestamp, duration):
            notes.append({
                "midi": midi, "string": string, "fret": fret,
                "start_seconds": start, "duration_seconds": timestamp - start,
            })
        if message.type == "note_on" and message.velocity:
            active[key] = timestamp
    return notes


def benchmark(archive: ZipFile, track: str):
    with TemporaryDirectory(prefix="riffroom-guitar-techs-") as folder:
        directory = Path(folder)
        original = directory / "micamp.wav"
        original.write_bytes(archive.read(f"P3_music/audio/micamp/micamp_{track}.wav"))
        end = soundfile.info(original).duration
        reference = load_reference(archive.read(f"P3_music/midi/midi_{track}.mid"), end)

        for audio_input in ("original", "guitar_stem"):
            started = perf_counter()
            path, bpm, _, source = _prepare_audio(original, directory, 0, end, audio_input)
            prep_seconds = perf_counter() - started
            if audio_input == "guitar_stem" and source != "demucs_guitar":
                raise RuntimeError(f"Guitar isolation failed for track {track}")
            if audio_input == "original":
                started = perf_counter()
                raw = transcribe_tabcnn(path, TAB_MODEL_PATH)
                yield "Raw TabCNN GuitarProFX / original", reference, raw, prep_seconds + perf_counter() - started

                started = perf_counter()
                pitches = optimize_fingering(_predict_notes(path, "basic_pitch", 0))
                yield "Basic Pitch + fingering / original", reference, pitches, prep_seconds + perf_counter() - started

            started = perf_counter()
            notes = _predict_notes(path, "tabcnn", 0)
            seconds = prep_seconds + perf_counter() - started
            yield f"Riffroom TabCNN polyphonic / {audio_input}", reference, notes, seconds
            if audio_input == "guitar_stem":
                started = perf_counter()
                lead = select_lead_notes(notes, bpm or 120, 0, end)
                yield f"Riffroom TabCNN lead / {audio_input}", reference, lead, seconds + perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Guitar-TECHS P3_music.zip")
    args = parser.parse_args()
    random.seed(42)
    totals = defaultdict(lambda: np.zeros(4, dtype=int))
    times = defaultdict(float)
    with ZipFile(args.archive) as archive:
        for number in range(1, 13):
            label = f"{number:02d}"
            for variant, reference, notes, seconds in benchmark(archive, label):
                times[variant] += seconds
                for tolerance in (0.05, 0.10):
                    counts = score(reference, notes, tolerance)
                    totals[variant, tolerance] += counts
                    if tolerance == 0.10:
                        show_result(f"{label} {variant}", counts, seconds)
    for (variant, tolerance), counts in totals.items():
        show_result(f"ALL {variant} {tolerance * 1000:.0f}ms", counts, times[variant])


if __name__ == "__main__":
    main()
