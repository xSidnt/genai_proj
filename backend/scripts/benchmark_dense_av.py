"""Compare audio-only and fixed-vision tabs on complete, time-bounded references."""

import argparse
from difflib import SequenceMatcher
from fractions import Fraction
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from time import perf_counter
from xml.etree import ElementTree

import pretty_midi

from app.audio.lead import select_lead_notes
from app.audio.media import extract_wav
from app.audio.notes import TranscriptionService
from app.transcription.api import HAND_MODEL_PATH, _predict_notes, _prepare_audio
from app.video.fretboard import FretboardCalibration
from app.video.vision import GuitarVisionService
from scripts.benchmark_egset12 import score


TUNING = TranscriptionService.STANDARD_TUNING


def read_score_positions(path: Path) -> list[tuple[int, int, int]]:
    """Read the tab part in score order, without duplicating tied note attacks."""
    root = ElementTree.parse(path).getroot()
    part = next(part for part in root.findall("part") if part.find(".//notations/technical/string") is not None)
    positions = []
    time = onset = Fraction(0)
    divisions = 1
    for measure in part.findall("measure"):
        measure_end = time
        for element in measure:
            if element.tag == "attributes":
                divisions = int(element.findtext("divisions", divisions))
            duration = Fraction(int(element.findtext("duration", "0")), divisions)
            if element.tag == "backup":
                time -= duration
            elif element.tag == "forward":
                time += duration
            elif element.tag == "note":
                if element.find("chord") is None:
                    onset = time
                    time += duration
                string = element.findtext("notations/technical/string")
                fret = element.findtext("notations/technical/fret")
                if string is not None and fret is not None and element.find("tie[@type='stop']") is None:
                    string, fret = int(string), int(fret)
                    positions.append((onset, TUNING[string] + fret, string, fret))
            measure_end = max(measure_end, time)
        time = measure_end
    return [(midi, string, fret) for _, midi, string, fret in sorted(positions)]


def load_reference(clip: dict, directory: Path) -> list[dict]:
    if "notes" in clip:
        return [
            dict(midi=TUNING[string] + fret, string=string, fret=fret, start_seconds=time, duration_seconds=0.1)
            for time, string, fret in clip["notes"]
        ]
    midi = pretty_midi.PrettyMIDI(str(directory / clip["midi"]))
    aligned = sorted((note.start, note.pitch, note.end) for track in midi.instruments for note in track.notes)
    positions = read_score_positions(directory / clip["musicxml"])
    blocks = SequenceMatcher(None, [p[0] for p in positions], [n[1] for n in aligned], autojunk=False).get_matching_blocks()
    matches = {block.b + i: positions[block.a + i][1:] for block in blocks for i in range(block.size)}
    offset = clip.get("video_offset", 0.0)
    notes = []
    for i, (start, pitch, end) in enumerate(aligned):
        string, fret = matches.get(i, (None, None))
        notes.append(dict(midi=pitch, string=string, fret=fret, start_seconds=start + offset, duration_seconds=end - start))
    return notes


def results(reference: list[dict], predictions: list[dict], tolerance: float) -> dict:
    ref, generated, pitch, _ = score(reference, predictions, tolerance)
    # Exclude timing neighborhoods where the score could not assign a string.
    unknown = [note["start_seconds"] for note in reference if note["string"] is None]
    eligible = lambda note: all(abs(note["start_seconds"] - start) > 2 * tolerance for start in unknown)
    tab_ref, tab_generated, _, tab = score(list(filter(eligible, reference)), list(filter(eligible, predictions)), tolerance)
    return {
        "reference": int(ref), "predictions": int(generated), "pitch_matches": int(pitch),
        "pitch_f1": float(2 * pitch / max(1, ref + generated)),
        "tab_reference": int(tab_ref), "tab_predictions": int(tab_generated), "tab_matches": int(tab),
        "tab_f1": float(2 * tab / max(1, tab_ref + tab_generated)),
    }


def evaluate(clip: dict, directory: Path, tolerances: list[float]) -> dict:
    video = directory / clip["video"]
    start, end = clip["range"]
    inside = lambda note: start <= note["start_seconds"] < end
    reference = list(filter(inside, load_reference(clip, directory)))
    if not reference:
        raise ValueError(f"No reference notes within range for {clip['name']}")
    calibration = FretboardCalibration.model_validate(clip["calibration"])
    runs = {}
    with TemporaryDirectory(prefix="riffroom-dense-av-") as temp:
        folder = Path(temp)
        wav = folder / "source.wav"
        extract_wav(video, wav)
        for audio in ("original", "guitar_stem"):
            random.seed(42)
            started = perf_counter()
            source, bpm, _, actual = _prepare_audio(wav, folder, start, end, audio)
            if audio == "guitar_stem" and actual != "demucs_guitar":
                raise RuntimeError(f"Isolation failed for {clip['name']}")
            notes = _predict_notes(source, "tabcnn", start)
            bpm = clip.get("bpm") or bpm or 120
            audio_seconds = perf_counter() - started
            mode = "lead" if audio == "guitar_stem" else "polyphonic"
            if mode == "lead":
                notes = select_lead_notes(notes, bpm, start, end)
            started = perf_counter()
            vision, _ = GuitarVisionService(HAND_MODEL_PATH).analyze(video, start, end, notes, bpm=bpm, calibration=calibration)
            vision_seconds = perf_counter() - started
            for label, predictions, elapsed in (("off", notes, audio_seconds), ("fixed", vision, audio_seconds + vision_seconds)):
                predictions = list(filter(inside, predictions))
                key = f"{audio}/{mode}/{label}"
                runs[key] = {
                    "bpm": bpm, "seconds": elapsed,
                    "scores": {str(round(t * 1000)): results(reference, predictions, t) for t in tolerances},
                }
    return {
        "name": clip["name"], "range": clip["range"], "reference_kind": clip["reference_kind"],
        "notes_without_string": sum(note["string"] is None for note in reference), "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    data = []
    for clip in manifest["clips"]:
        row = evaluate(clip, args.manifest.parent, [0.05, 0.10])
        data.append(row)
        print(json.dumps(row), flush=True)
    if args.output:
        args.output.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
