from math import ceil, floor


def select_lead_notes(notes: list[dict], bpm: int, start: float, end: float) -> list[dict]:
    """Select one detected attack per sixteenth-note slot in the analysis range."""
    step = 15 / bpm
    first_slot = ceil(start / step - 1e-9)
    last_slot = max(first_slot, ceil(end / step - 1e-9) - 1)
    winners: dict[int, tuple[float, dict]] = {}

    for note in notes:
        onset = note["start_seconds"]
        if not start <= onset < end:
            continue

        slot = min(last_slot, max(first_slot, floor(onset / step + 0.5)))
        grid_time = slot * step
        score = note["confidence"] + 0.25 * note.get("attack_confidence", 0)
        score -= 0.15 * abs(onset - grid_time) / step
        if slot not in winners or score > winners[slot][0]:
            winners[slot] = (score, dict(note, grid_seconds=grid_time))

    # Keep the measured onsets for vision and technique analysis. Only display uses the slot.
    return [winners[slot][1] for slot in sorted(winners)]
