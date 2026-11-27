"""Score Riffroom's audio pipeline on matching EGSet12 WAV and JAMS files."""

import argparse
import json
import random
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import librosa
import mir_eval
import numpy as np

from app.audio.fingering import optimize_fingering
from app.audio.lead import select_lead_notes
from app.audio.notes import TranscriptionService
from app.audio.tabcnn import HOP_LENGTH, SAMPLE_RATE, _decode_notes, _load_model, transcribe_tabcnn
from app.transcription.api import TAB_MODEL_PATH, _predict_notes, _prepare_audio


def load_reference(annotation: Path) -> tuple[float, list[dict]]:
    data = json.loads(annotation.read_text())
    notes = []
    for track in data["annotations"]:
        if track["namespace"] != "note_midi":
            continue
        # EGSet12 numbers its strings from low to high, starting at zero.
        string = 6 - int(track["annotation_metadata"]["data_source"])
        open_pitch = TranscriptionService.STANDARD_TUNING[string]
        for event in track["data"]:
            pitch = int(event["value"])
            if event["duration"] > 0:
                notes.append({
                    "midi": pitch,
                    "string": string,
                    "fret": pitch - open_pitch,
                    "start_seconds": event["time"],
                    "duration_seconds": event["duration"],
                })
    return float(data["file_metadata"]["duration"]), notes


def count_matches(reference: list[dict], generated: list[dict], onset_tolerance: float) -> int:
    if not reference or not generated:
        return 0

    def events(notes):
        intervals = np.array([
            (note["start_seconds"], note["start_seconds"] + note["duration_seconds"])
            for note in notes
        ])
        return intervals, librosa.midi_to_hz([note["midi"] for note in notes])

    return len(mir_eval.transcription.match_notes(
        *events(reference), *events(generated), onset_tolerance=onset_tolerance, offset_ratio=None,
    ))


def score(reference: list[dict], generated: list[dict], onset_tolerance: float = 0.05) -> np.ndarray:
    generated = [note for note in generated if note["duration_seconds"] > 0]
    pitch_matches = count_matches(reference, generated, onset_tolerance)
    tab_matches = sum(count_matches(
        [note for note in reference if note["string"] == string],
        [note for note in generated if note["string"] == string],
        onset_tolerance,
    ) for string in range(1, 7))
    return np.array([len(reference), len(generated), pitch_matches, tab_matches])


def show_result(label: str, counts: np.ndarray, seconds: float) -> None:
    reference, generated, pitch, tab = counts
    denominator = max(1, reference + generated)
    print(
        f"{label:36}  pitch F1 {2 * pitch / denominator:6.1%}  "
        f"tab F1 {2 * tab / denominator:6.1%}  "
        f"exact string/fret {tab}/{pitch} pitch matches  "
        f"{generated}/{reference} generated/reference notes  {seconds:.1f}s",
        flush=True,
    )


def transcribe_original_tabcnn(audio_path: Path, weights: Path) -> list[dict]:
    # Original TabCNN uses peak-normalized audio and raw CQT magnitude.
    audio, _ = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    audio = librosa.util.normalize(audio)
    spectrum = np.abs(librosa.cqt(audio, sr=SAMPLE_RATE, hop_length=HOP_LENGTH, n_bins=192, bins_per_octave=24))
    padded = np.pad(spectrum, ((0, 0), (4, 4)))
    windows = np.lib.stride_tricks.sliding_window_view(padded, 9, axis=1)
    inputs = np.ascontiguousarray(windows.transpose(1, 0, 2)[..., None], dtype=np.float32)
    probabilities = np.exp(_load_model(weights).run(["output"], {"input": inputs})[0])
    return _decode_notes(probabilities, len(audio) / SAMPLE_RATE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing the WAV and JAMS pairs")
    parser.add_argument("--include-isolated", action="store_true", help="Test both note models with guitar isolation as well")
    parser.add_argument("--original-tabcnn-weights", type=Path, help="Also score standalone TabCNN and GuitarProFX on original audio")
    args = parser.parse_args()
    random.seed(42)  # Demucs uses a randomly shifted input.
    clips = [(wav, wav.with_suffix(".jams")) for wav in sorted(args.directory.glob("*.wav"))]
    clips = [(wav, annotation) for wav, annotation in clips if annotation.is_file()]
    if not clips:
        parser.error("No matching WAV and JAMS pairs found")

    variants = {"original": ("basic_pitch", "tabcnn")}
    if args.include_isolated:
        variants["guitar_stem"] = variants["original"]
    modes = ("polyphonic", "lead")
    totals = {
        (model, audio_input, mode): np.zeros(4, dtype=int)
        for audio_input, models in variants.items() for model in models for mode in modes
    }
    durations = dict.fromkeys(totals, 0.0)
    baseline_counts = None
    if args.original_tabcnn_weights is not None:
        baseline_counts = {model: np.zeros(4, dtype=int) for model in ("Original TabCNN", "Raw GuitarProFX TabCNN")}
        baseline_times = dict.fromkeys(baseline_counts, 0.0)
    for wav, annotation in clips:
        duration, reference = load_reference(annotation)
        for audio_input, models in variants.items():
            prep_started = perf_counter()
            with TemporaryDirectory(prefix="riffroom-benchmark-") as directory:
                path, bpm, _, source = _prepare_audio(wav, Path(directory), 0, duration, audio_input)
                prep_seconds = perf_counter() - prep_started
                if audio_input == "guitar_stem" and source != "demucs_guitar":
                    raise RuntimeError(f"Isolation failed for {wav.name}")
                if audio_input == "original" and baseline_counts is not None:
                    started = perf_counter()
                    plain = transcribe_original_tabcnn(path, args.original_tabcnn_weights)
                    baseline_times["Original TabCNN"] += prep_seconds + perf_counter() - started
                    started = perf_counter()
                    guitarprofx = transcribe_tabcnn(path, TAB_MODEL_PATH)
                    baseline_times["Raw GuitarProFX TabCNN"] += prep_seconds + perf_counter() - started
                    baseline_counts["Original TabCNN"] += score(reference, plain)
                    baseline_counts["Raw GuitarProFX TabCNN"] += score(reference, guitarprofx)
                for model in models:
                    started = perf_counter()
                    raw_notes = _predict_notes(path, model, 0)
                    inference_seconds = perf_counter() - started
                    for mode in modes:
                        started = perf_counter()
                        notes = select_lead_notes(raw_notes, bpm or 120, 0, duration) if mode == "lead" else raw_notes
                        if model == "basic_pitch":
                            notes = optimize_fingering(notes)
                        elapsed = prep_seconds + inference_seconds + perf_counter() - started
                        variant = (model, audio_input, mode)
                        counts = score(reference, notes)
                        totals[variant] += counts
                        durations[variant] += elapsed
                        show_result(f"{wav.stem} {' / '.join(variant)}", counts, elapsed)

    for variant in totals:
        show_result(f"All {len(clips)} clips: {' / '.join(variant)}", totals[variant], durations[variant])
    if baseline_counts is not None:
        for model, counts in baseline_counts.items():
            show_result(f"All {len(clips)} clips: {model}", counts, baseline_times[model])


if __name__ == "__main__":
    main()
