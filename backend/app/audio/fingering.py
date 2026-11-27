from dataclasses import dataclass

from app.audio.notes import TranscriptionService

FretEvidence = dict[tuple[int, int], float]


@dataclass(frozen=True)
class HandPosition:
    anchor_fret: float
    from_index: bool = True

    def distance(self, fret: int) -> float:
        if fret == 0:
            return 0.0
        # Allow for camera error, a backward reach, and a stretch toward the bridge.
        backward_reach = 1.25 if self.from_index else 1.65
        return max(0.0, self.anchor_fret - backward_reach - fret, fret - self.anchor_fret - 4.5)

    def allows(self, position: tuple[int, int], evidence: FretEvidence) -> bool:
        return self.distance(position[1]) == 0 or evidence.get(position, 0) >= 0.65


@dataclass(frozen=True)
class Path:
    cost: float
    positions: tuple[tuple[int, int], ...]
    hand_fret: float | None
    strings_in_chord: frozenset[int]
    frets_in_chord: tuple[int, ...]


def pitch_positions(pitch: int) -> list[tuple[int, int]]:
    return [(string, pitch - tuning) for string, tuning in TranscriptionService.STANDARD_TUNING.items()
            if 0 <= pitch - tuning <= 24]


def optimize_fingering(
    notes: list[dict],
    visual_evidence: list[FretEvidence] | None = None,
    hand_positions: list[HandPosition | None] | None = None,
    finger_evidence: list[FretEvidence] | None = None,
) -> list[dict]:
    """Search pitch-compatible paths using fingertip and hand position evidence."""
    paths = [Path(0, (), None, frozenset(), ())]
    chord_start = float("-inf")
    previous_hand = None
    for index, note in enumerate(notes):
        timestamp = note["start_seconds"]
        new_chord = timestamp - chord_start > 0.032
        new_phrase = timestamp - chord_start > 0.65
        if new_chord:
            chord_start = timestamp
        single_note = new_chord and (
            index + 1 == len(notes) or notes[index + 1]["start_seconds"] - timestamp > 0.032
        )

        pitch = note["midi"]
        choices = pitch_positions(pitch)
        if not choices:
            choices = [(note["string"], note["fret"])]

        observed = visual_evidence[index] if visual_evidence is not None else {}
        fingers = finger_evidence[index] if finger_evidence is not None else {}
        hand = hand_positions[index] if hand_positions is not None else None
        hand_shift = 0.0
        if new_chord and hand and previous_hand and hand.from_index and previous_hand.from_index:
            hand_shift = hand.anchor_fret - previous_hand.anchor_fret
        previous_hand = hand
        original = (note["string"], note["fret"])
        next_paths = {}
        outside_hand_paths = {}
        conflicting_paths = {}
        for path in paths:
            anchor = None if new_phrase else path.hand_fret
            strings = frozenset() if new_chord else path.strings_in_chord
            frets = () if new_chord else path.frets_in_chord
            for string, fret in choices:
                position = (string, fret)
                cost = path.cost + 0.08 * fret + (0.3 if fret == 0 else 0) - fingers.get(position, 0)
                if visual_evidence is not None:
                    cost -= 4 * observed.get(position, 0)
                    if position != original:
                        cost += 1.1 + 0.8 * note["confidence"]
                if fret and anchor is not None:
                    cost += 0.65 * abs(fret - anchor - hand_shift)
                outside_hand = hand is not None and not hand.allows(position, observed)
                if outside_hand:
                    cost += 3.0 + min(3.0, hand.distance(fret))
                next_frets = (*frets, fret) if fret else frets
                if len(next_frets) > 1:
                    cost += 2 * max(0, max(next_frets) - min(next_frets) - 4)
                hand_fret = sum(next_frets) / len(next_frets) if next_frets else anchor
                next_strings = strings | {string}
                key = (hand_fret, next_strings, next_frets)
                if string in strings:
                    candidates = conflicting_paths
                elif outside_hand and single_note:
                    candidates = outside_hand_paths
                else:
                    candidates = next_paths
                previous = candidates.get(key)
                if previous is None or cost < previous.cost:
                    candidates[key] = Path(cost, (*path.positions, position), hand_fret, next_strings, next_frets)
        # Preserve pitch detections when the input has more notes than can fit on distinct strings.
        paths = sorted(
            (next_paths or outside_hand_paths or conflicting_paths).values(),
            key=lambda candidate: candidate.cost,
        )[:40]

    return [dict(note, string=string, fret=fret)
            for note, (string, fret) in zip(notes, paths[0].positions)]
