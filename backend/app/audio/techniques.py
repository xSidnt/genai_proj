from collections import defaultdict
from statistics import median


def add_attack_and_bend_evidence(notes: list[dict], attacks: list[dict]) -> list[dict]:
    """Use pitch-compatible audio attacks to split repeated TabCNN positions."""
    by_pitch = defaultdict(list)
    for attack in attacks:
        by_pitch[attack["midi"]].append(attack)

    result = []
    for note in notes:
        start = note["start_seconds"]
        end = start + note["duration_seconds"]
        candidates = by_pitch[note["midi"]]
        splits = [start]
        for attack in candidates:
            timestamp = attack["start_seconds"]
            if attack["confidence"] >= 0.5 and splits[-1] + 0.065 <= timestamp <= end - 0.065:
                splits.append(timestamp)

        for onset, offset in zip(splits, [*splits[1:], end]):
            matches = [attack for attack in candidates if abs(onset - attack["start_seconds"]) <= 0.055]
            evidence = min(matches, key=lambda attack: abs(onset - attack["start_seconds"]), default={})
            result.append(dict(
                note, start_seconds=onset, duration_seconds=round(offset - onset, 3),
                bend_curve=evidence.get("bend_curve", []),
                attack_confidence=evidence.get("confidence", 0),
            ))

    return sorted(result, key=lambda note: note["start_seconds"])


def annotate_techniques(notes: list[dict]) -> None:
    next_on_string = {}
    for note in reversed(notes):
        string = note["string"]
        following = next_on_string.get(string)
        next_on_string[string] = note
        curve = note.pop("bend_curve", [])
        note.pop("attack_confidence", None)
        if len(curve) < 5 or note["duration_seconds"] < 0.10:
            continue

        smoothed = [median(curve[index:index + 3]) for index in range(len(curve) - 2)]
        start_pitch = median(smoothed[:max(1, len(smoothed) // 5)])
        end_pitch = median(smoothed[-max(1, len(smoothed) // 5):])
        excursion = end_pitch - start_pitch
        if following is not None:
            interval = following["midi"] - note["midi"]
            gap = following["start_seconds"] - note["start_seconds"] - note["duration_seconds"]
            if -0.04 <= gap <= 0.09 and interval and abs(excursion) >= 0.75 and abs(interval - excursion) <= 0.65:
                note.update(technique="slide", technique_target_fret=following["fret"])
                continue

        bend = max(smoothed) - start_pitch
        if bend >= 0.75:
            note.update(technique="bend", bend_semitones=round(bend * 2) / 2)
