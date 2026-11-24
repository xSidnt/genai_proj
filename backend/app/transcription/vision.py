from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision as mp_vision

from app.transcription.jev_vision import JevVisionService


class GuitarVisionService:
    COARSE_INTERVAL_SECONDS = 0.5

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path

    def analyze(
        self,
        video_path: Path,
        start_seconds: float,
        end_seconds: float,
        notes: list[dict],
        bpm: int | None = None,
    ) -> tuple[list[dict], list[dict]]:
        if not video_path.exists():
            return notes, []

        landmarker = self._create_landmarker()
        if landmarker is None:
            enhanced = [dict(note, vision_status="unavailable", visual_confidence=0.0) for note in notes]
            return enhanced, []

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            landmarker.close()
            return [dict(note, vision_status="unavailable", visual_confidence=0.0) for note in notes], []

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        coarse = []
        timestamps = np.arange(start_seconds, end_seconds + 0.001, self.COARSE_INTERVAL_SECONDS)
        for timestamp in timestamps:
            frame = self._read_frame(capture, float(timestamp), fps)
            if frame is None:
                continue
            observation = self._observe_frame(frame, landmarker)
            coarse.append({
                "timestamp_seconds": round(float(timestamp), 3),
                **observation,
            })

        jev = JevVisionService()
        subdivision_seconds = 60 / (bpm or 120) / 4
        subdivision_cache: dict[tuple[int, int], tuple[np.ndarray | None, dict]] = {}
        enhanced_notes = []
        for note in notes:
            timestamp = float(note["start_seconds"])
            midi = int(note["midi"])
            subdivision = round((timestamp - start_seconds) / subdivision_seconds)
            cache_key = (subdivision, midi)
            if cache_key not in subdivision_cache:
                subdivision_timestamp = start_seconds + subdivision * subdivision_seconds
                frame = self._read_frame(capture, subdivision_timestamp, fps)
                jev_result = jev.infer_position(frame, midi)
                subdivision_cache[cache_key] = (frame, jev_result)
            else:
                frame, jev_result = subdivision_cache[cache_key]

            observation = self._observe_frame(frame, landmarker) if frame is not None else {
                "hands_visible": 0,
                "fretting_hand_visible": False,
                "neck_visible": False,
                "visual_confidence": 0.0,
            }

            visual_confidence = max(
                float(observation["visual_confidence"]),
                float(jev_result["visual_confidence"]),
            )
            combined_confidence = min(
                1.0,
                float(note["confidence"])
                * (0.55 + 0.45 * visual_confidence),
            )

            visual_status = jev_result["visual_status"]
            if visual_status == "unavailable":
                visual_status = "hand-visible" if observation["hands_visible"] > 0 else "hand-not-visible"

            enhanced_note = dict(
                note,
                visual_status=visual_status,
                visual_confidence=round(visual_confidence, 3),
                combined_confidence=round(combined_confidence, 3),
                visual_string=jev_result["visual_string"],
                visual_fret=jev_result["visual_fret"],
                jev_answer=jev_result["jev_answer"],
                jev_probabilities=jev_result["jev_probabilities"],
                answer_mass=jev_result["answer_mass"],
            )

            if jev_result["visual_string"] is not None:
                enhanced_note["string"] = int(jev_result["visual_string"])
                enhanced_note["fret"] = int(jev_result["visual_fret"])

            enhanced_notes.append(enhanced_note)

        capture.release()
        landmarker.close()
        return enhanced_notes, coarse

    def _create_landmarker(self):
        if not self.model_path.exists():
            return None
        base_options = python.BaseOptions(model_asset_path=str(self.model_path))
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return mp_vision.HandLandmarker.create_from_options(options)

    @staticmethod
    def _read_frame(capture: cv2.VideoCapture, timestamp: float, fps: float):
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(timestamp * fps))))
        ok, frame = capture.read()
        return frame if ok else None

    @staticmethod
    def _observe_frame(frame: np.ndarray, landmarker) -> dict:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

        hands_visible = len(result.hand_landmarks)
        if hands_visible == 0:
            neck_visible = False
            fretting_visible = False
            visual_confidence = 0.0
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 80, 180)
            edge_density = float(np.count_nonzero(edges)) / float(edges.size)
            neck_visible = edge_density > 0.035
            fretting_visible = any(
                0.05 < landmark[8].y < 0.95
                and 0.05 < landmark[8].x < 0.95
                for landmark in result.hand_landmarks
            )
            visual_confidence = 0.35 + (0.25 if neck_visible else 0.0) + (0.25 if fretting_visible else 0.0)

        return {
            "hands_visible": hands_visible,
            "fretting_hand_visible": fretting_visible,
            "neck_visible": neck_visible,
            "visual_confidence": round(min(visual_confidence, 1.0), 3),
        }
