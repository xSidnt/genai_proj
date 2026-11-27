from collections import defaultdict

import cv2
import mediapipe as mp
import numpy as np

from app.audio.fingering import FretEvidence, HandPosition, optimize_fingering
from app.video.finger_evidence import assign_fingers, score_fingers
from app.video.fretboard import Fretboard
from app.video.fretboard_tracking import FretboardTracker


def analyze_calibrated(
    capture: cv2.VideoCapture,
    landmarker,
    fretboard: Fretboard,
    start: float,
    end: float,
    notes: list[dict],
    observation_interval: float,
    bpm: int = 120,
) -> tuple[list[dict], list[dict]]:
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    first_frame = max(0, int(np.floor(start * fps)))
    last_frame = max(first_frame, int(np.ceil(end * fps)) - 1)
    observation_times = defaultdict(list)
    for timestamp in np.arange(start, end + 0.001, observation_interval):
        observation_times[min(round(timestamp * fps), last_frame)].append(round(float(timestamp), 3))

    neighbor = max(1, round(0.035 * fps))
    note_frames = []
    for note in notes:
        frame = round(float(note["start_seconds"]) * fps)
        note_frames.append(tuple(sorted({
            min(last_frame, max(first_frame, frame + offset)) for offset in (-neighbor, 0, neighbor)
        })))

    observations = []
    hands_by_frame = {}
    tracking_enabled = fretboard.reference_seconds is not None
    tracker, reference_frame = _make_tracker(capture, fretboard, fps) if tracking_enabled else (None, None)
    measure_frames = set()
    tracking_frames = set()
    if tracker is not None:
        measure_seconds = 240 / bpm
        first_boundary = np.ceil(start / measure_seconds) * measure_seconds
        measure_frames = {first_frame, *(
            min(last_frame, round(timestamp * fps))
            for timestamp in np.arange(first_boundary, end, measure_seconds)
        )}
        tracking_frames = set(range(first_frame, last_frame + 1, max(1, round(fps * 0.10))))
        if reference_frame is not None and first_frame <= reference_frame <= last_frame:
            tracking_frames.add(reference_frame)
        for frame in measure_frames:
            if frame not in observation_times:
                observation_times[frame].append(round(frame / fps, 3))

    sample_frames = observation_times.keys() | {frame for group in note_frames for frame in group}
    frames = sorted(sample_frames | measure_frames | tracking_frames)
    capture.set(cv2.CAP_PROP_POS_FRAMES, frames[0])
    current_frame = frames[0] - 1
    tracked_corners = None
    next_retry = first_frame

    for frame_number in frames:
        while current_frame < frame_number:
            if not capture.grab():
                break
            current_frame += 1
        if current_frame < frame_number:
            break

        ok, frame = capture.retrieve()
        if not ok:
            continue

        if tracker is not None:
            reanchor = frame_number in measure_frames or (tracked_corners is None and frame_number >= next_retry)
            tracked_corners = tracker.update(
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                reference_frame=frame_number == reference_frame,
                reanchor=reanchor,
            )
            if reanchor:
                next_retry = frame_number + max(1, round(fps * 0.5))

        if frame_number not in sample_frames:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        landmarks = landmarker.detect_for_video(image, round(1000 * frame_number / fps))
        neck_visible = tracked_corners is not None or not tracking_enabled
        fretting_visible = False
        if neck_visible:
            hand = fretboard.observe_hands(landmarks.hand_landmarks, tracked_corners)
            hands_by_frame[frame_number] = hand
            fretting_visible = bool(len(hand.fingertips))
        for timestamp in observation_times.get(frame_number, ()):
            observations.append({
                "timestamp_seconds": timestamp,
                "hands_visible": len(landmarks.hand_landmarks),
                "fretting_hand_visible": fretting_visible,
                "neck_visible": neck_visible,
                "visual_confidence": 0.0,
                "measure_anchor": frame_number in measure_frames,
                "fretboard_reanchored": bool(tracker and tracker.reanchored),
            })

    cached_scores: dict[tuple[int, int], FretEvidence] = {}
    evidence = []
    hand_positions = []
    finger_scores = []
    for note, group in zip(notes, note_frames):
        pitch = int(note["midi"])
        samples = []
        hand_samples = []
        for frame in group:
            if frame not in hands_by_frame:
                continue
            hand = hands_by_frame[frame]
            key = (frame, pitch)
            if key not in cached_scores:
                cached_scores[key] = fretboard.score_pitch(pitch, hand.fingertips)
            samples.append(cached_scores[key])
            if hand.position is not None:
                hand_samples.append(hand.position)
        evidence.append(_merge_frame_scores(samples))
        hand_position = _stable_hand_position(hand_samples)
        hand_positions.append(hand_position)
        finger_scores.append(score_fingers(pitch, [hands_by_frame.get(frame) for frame in group], hand_position))

    finger_evidence = [{position: max(fingers.values()) for position, fingers in scores.items()} for scores in finger_scores]
    selected = (
        optimize_fingering(notes, evidence, hand_positions, finger_evidence)
        if any(evidence) or any(hand_positions) or any(finger_evidence) else notes
    )
    fingers = assign_fingers(selected, finger_scores)
    return [
        _annotate_note(original, optimized, observed, hand, finger)
        for original, optimized, observed, hand, finger in zip(notes, selected, evidence, hand_positions, fingers)
    ], observations


def _make_tracker(capture: cv2.VideoCapture, fretboard: Fretboard, fps: float):
    if fretboard.reference_seconds is None:
        return None, None
    reference_frame = int(fretboard.reference_seconds * fps + 0.001)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count > 0:
        reference_frame = min(reference_frame, frame_count - 1)
    capture.set(cv2.CAP_PROP_POS_FRAMES, reference_frame)
    ok, frame = capture.read()
    if not ok:
        return None, None
    return FretboardTracker(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), fretboard.image_points), reference_frame


def _merge_frame_scores(samples: list[FretEvidence]) -> FretEvidence:
    merged = {}
    for position in {position for sample in samples for position in sample}:
        values = [sample.get(position, 0.0) for sample in samples]
        merged[position] = 0.45 * max(values) + 0.55 * sum(values) / len(values)
    return merged


def _stable_hand_position(samples: list[HandPosition]) -> HandPosition | None:
    if len(samples) < 2:
        return None
    center = float(np.median([sample.anchor_fret for sample in samples]))
    inliers = [sample for sample in samples if abs(center - sample.anchor_fret) <= 0.65]
    if len(inliers) < 2:
        return None
    indexes = [sample.anchor_fret for sample in inliers if sample.from_index]
    if len(indexes) >= 2:
        return HandPosition(sum(indexes) / len(indexes))
    return HandPosition(sum(sample.anchor_fret for sample in inliers) / len(inliers), from_index=False)


def _annotate_note(
    original: dict, selected: dict, evidence: FretEvidence, hand: HandPosition | None, finger: str = "unknown",
) -> dict:
    position = (selected["string"], selected["fret"])
    strength = evidence.get(position, 0)
    result = dict(selected, audio_string=original["string"], audio_fret=original["fret"], visual_confidence=round(strength, 3))
    if hand is not None:
        field = "visual_index_fret" if hand.from_index else "visual_hand_fret"
        result[field] = round(hand.anchor_fret, 1)
        if not hand.allows(position, evidence):
            return dict(result, visual_status="calibrated-conflict")
    result["finger"] = finger
    if strength >= 0.5:
        return dict(result, visual_status="calibrated-visible", visual_string=position[0], visual_fret=position[1])
    changed = position != (original["string"], original["fret"])
    if changed and hand is not None and position[1] != 0:
        return dict(result, visual_status="calibrated-hand")
    return dict(result, visual_status="calibrated-inferred" if changed else "calibrated-uncertain")
