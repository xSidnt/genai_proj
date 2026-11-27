from app.audio.fingering import HandPosition, pitch_positions
from app.video.fretboard import HandObservation

FINGER_NAMES = ("index", "middle", "ring", "pinky")
FingerEvidence = dict[tuple[int, int], dict[str, float]]


def score_fingers(
    pitch: int,
    frames: list[HandObservation | None],
    index: HandPosition | None,
) -> FingerEvidence:
    """Score named fingertips against the pitch-compatible positions near an attack."""
    scores = {}
    for string, fret in pitch_positions(pitch):
        if fret == 0:
            continue
        string_axis = 6 - string
        zone_low = 2 * (string_axis // 2) - 0.5
        zone_high = zone_low + 2
        for offset, finger in enumerate(FINGER_NAMES):
            samples = []
            distances = []
            for frame in frames:
                tip = frame.fingers[offset] if frame is not None and frame.fingers else None
                if tip is None:
                    continue
                tip_fret, tip_axis = tip
                fret_error = abs(tip_fret - fret)
                string_error = abs(tip_axis - string_axis)
                zone_error = max(0.0, zone_low - tip_axis, tip_axis - zone_high)
                fret_fit = max(0.0, 1 - fret_error / 1.25)
                zone_fit = max(0.0, 1 - zone_error / 0.9)
                string_fit = max(0.0, 1 - string_error / 1.5)
                index_tip = frame.fingers[0]
                if offset and index is not None and index.from_index and index_tip is not None:
                    index_axis = index_tip[1]
                    if abs(tip_axis - index_axis) >= 1 and (tip_axis - index_axis) * (string_axis - index_axis) < 0:
                        zone_fit *= 0.7
                samples.append(fret_fit * zone_fit * (0.72 + 0.28 * string_fit))
                distances.append(fret_error + 0.5 * string_error)
            if len(samples) < 2:
                continue
            fit = 0.5 * max(samples) + 0.5 * sum(samples) / len(samples)
            if fit <= 0:
                continue
            # A fingertip approaching the candidate around the attack helps distinguish resting fingers.
            approach = max(0.0, distances[0] - min(distances[1:]))
            fit *= 0.9 + 0.1 * min(1.0, approach)
            if index is not None and index.from_index:
                expected_fret = index.anchor_fret + offset
                # One finger per fret is a preference. Allow same-fret reaches and stretches.
                fit *= max(0.72, 1 - 0.08 * abs(fret - expected_fret))
            scores.setdefault((string, fret), {})[finger] = fit
    return scores


def _choose_finger(scores: dict[str, float]) -> str:
    ranked = sorted(scores.items(), key=lambda result: result[1], reverse=True)
    if not ranked:
        return "unknown"
    finger, support = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    return finger if support >= 0.55 and support - runner_up >= 0.12 else "unknown"


def assign_fingers(notes: list[dict], evidence: list[FingerEvidence]) -> list[str]:
    assignments = []
    chord_start = float("-inf")
    chord_fingers = {}
    for i, (note, scores) in enumerate(zip(notes, evidence)):
        if note["start_seconds"] - chord_start > 0.032:
            chord_start = note["start_seconds"]
            chord_fingers = {}
        position = (note["string"], note["fret"])
        finger = _choose_finger(scores.get(position, {}))
        assignments.append(finger)
        if finger == "unknown":
            continue
        matches = chord_fingers.setdefault(finger, [])
        matches.append((i, position[1]))
        if len({fret for _, fret in matches}) > 1:
            # A finger can barre the same fret. Different frets make its assignment ambiguous.
            for match, _ in matches:
                assignments[match] = "unknown"
    return assignments
