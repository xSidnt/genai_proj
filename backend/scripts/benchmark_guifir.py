"""Evaluate calibrated Riffroom on public GuiFiR-Vid test clips without a capo."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from time import perf_counter

import cv2
import numpy as np

from app.audio.lead import select_lead_notes
from app.audio.media import extract_wav
from app.audio.notes import TranscriptionService
from app.transcription.api import HAND_MODEL_PATH, _predict_notes, _prepare_audio
from app.video.fretboard import FretboardCalibration, ImagePoint
from app.video.vision import GuitarVisionService
from scripts.benchmark_egset12 import score


def frame_number(row: dict) -> int:
    # The filename carries the source frame. frame_id indexes the annotations.
    return int(Path(row["filename"]).stem.rsplit("_", 1)[1]) - 1


def load_clips(path: Path) -> dict[str, list[dict]]:
    clips = defaultdict(list)
    with path.open() as source:
        for line in source:
            row = json.loads(line)
            if row["frame_capo"] == 0:
                clips[row["filename"].split("/")[0]].append(row)
    return {name: sorted(rows, key=frame_number) for name, rows in sorted(clips.items())}


def make_calibration(row: dict) -> FretboardCalibration:
    # GuiFiR annotates the nut and fret 20 in a 640 by 360 coordinate space.
    pose = row["frame_gt_pose"]
    return FretboardCalibration(
        start_fret=0,
        reference_fret=20,
        points=tuple(ImagePoint(x=pose[key][0] / 640, y=pose[key][1] / 360) for key in ("rt", "rb", "lb", "lt")),
    )


def load_attacks(rows: list[dict], fps: float) -> list[dict]:
    return [
        {
            "string": string,
            "fret": fret,
            "midi": TranscriptionService.STANDARD_TUNING[string] + fret,
            "start_seconds": frame_number(row) / fps,
            "duration_seconds": 1 / fps,
        }
        for row in rows
        for string, fret in enumerate(row["frame_tab"], start=1)
        # The released JSONL uses 20 for an inactive string.
        if 0 <= fret < 20
    ]


def clip_time(path: Path) -> tuple[float, int]:
    capture = cv2.VideoCapture(str(path))
    try:
        return capture.get(cv2.CAP_PROP_FPS), int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()


def evaluate(
    path: Path, rows: list[dict], tempo_override: int | None, annotation_fps: float,
) -> tuple[list[dict], dict[str, list[dict]], float, int]:
    fps, frame_count = clip_time(path)
    if fps <= 0 or frame_count <= 0 or frame_number(rows[-1]) / annotation_fps >= frame_count / fps:
        raise ValueError(f"Check annotation frame numbers and FPS for {path.name}")
    end = frame_count / fps

    calibration = make_calibration(rows[0])
    reference = load_attacks(rows[1:], annotation_fps)
    random.seed(path.stem)
    with TemporaryDirectory(prefix="riffroom-guifir-") as folder:
        directory = Path(folder)
        original = directory / "source.wav"
        extract_wav(path, original)
        audio, bpm, _, _ = _prepare_audio(original, directory, 0, end, "original")
        clean_notes = _predict_notes(audio, "tabcnn", 0)
        stem, _, _, source = _prepare_audio(original, directory, 0, end, "guitar_stem")
        if source != "demucs_guitar":
            raise RuntimeError(f"Guitar isolation failed for {path.name}")
        stem_notes = _predict_notes(stem, "tabcnn", 0)
        grid_bpm = tempo_override or bpm or 120
        lead = select_lead_notes(stem_notes, grid_bpm, 0, end)
        started = perf_counter()
        fixed, _ = GuitarVisionService(HAND_MODEL_PATH).analyze(path, 0, end, lead, bpm=grid_bpm, calibration=calibration)
        vision_seconds = perf_counter() - started
    return reference, {
        "original / polyphonic": clean_notes,
        "isolated / polyphonic": stem_notes,
        "isolated / lead": lead,
        "isolated / lead / fixed": fixed,
    }, vision_seconds, grid_bpm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", type=Path, help="Directory of extracted GuiFiR raw clips")
    parser.add_argument("annotations", type=Path, help="guifir_test_coco_anno_box.jsonl")
    parser.add_argument("--clips", nargs="+", help="Optional clip stems to evaluate")
    parser.add_argument("--grid-bpm", type=int, help="Override each clip's detected BPM")
    parser.add_argument("--annotation-fps", type=float, default=30, help="Frame rate of the annotation timeline")
    args = parser.parse_args()
    if args.annotation_fps <= 0:
        parser.error("--annotation-fps must be positive")
    if args.grid_bpm is not None and not 30 <= args.grid_bpm <= 300:
        parser.error("--grid-bpm must be between 30 and 300")
    clips = load_clips(args.annotations)
    names = args.clips or list(clips)
    missing = [name for name in names if name not in clips or not (args.videos / f"{name}.mp4").is_file()]
    if missing:
        parser.error(f"Missing no-capo test clips or labels: {', '.join(missing)}")

    tolerances = (0.05, 0.10)
    totals = defaultdict(lambda: np.zeros(4, dtype=int))
    labeled_fingers = 0
    vision_time = 0.0
    for name in names:
        reference, candidates, seconds, bpm = evaluate(
            args.videos / f"{name}.mp4", clips[name], args.grid_bpm, args.annotation_fps,
        )
        vision_time += seconds
        for variant, notes in candidates.items():
            for tolerance in tolerances:
                counts = score(reference, notes, tolerance)
                totals[variant, tolerance] += counts
                print(name, variant, round(tolerance * 1000), *counts, f"{bpm} BPM", flush=True)
            if variant.endswith("fixed"):
                labeled_fingers += sum(note.get("finger", "unknown") != "unknown" for note in notes)

    for (variant, tolerance), (reference, generated, pitch, tab) in totals.items():
        print(f"ALL {variant} {tolerance * 1000:.0f}ms "
              f"pitch recall {pitch / reference:.1%} ({pitch}/{reference}), "
              f"tab recall {tab / reference:.1%} ({tab}/{reference}), "
              f"{tab}/{pitch} matched pitches assigned to the right string, {generated} output notes")
    print(f"{len(names)} clips, {labeled_fingers} finger estimates, {vision_time:.2f}s vision time")


if __name__ == "__main__":
    main()
