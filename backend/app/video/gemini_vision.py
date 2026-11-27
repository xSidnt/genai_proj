import base64
import json
import logging
import os
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class GeminiVisionService:
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        load_dotenv(backend_dir / ".env")
        load_dotenv(backend_dir.parent / ".env")
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.enabled = bool(self.api_key)
        self.client = None

    def infer_position(self, frame: np.ndarray | None, midi: int) -> dict:
        if frame is None:
            return self._unavailable()
        if not self.enabled:
            return self._unavailable()

        candidates = self._pitch_candidates(midi)
        if not candidates:
            return self._unavailable()

        try:
            from google import genai
            from google.genai import types

            if self.client is None:
                self.client = genai.Client(api_key=self.api_key)

            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                return self._unavailable()

            candidate_text = ", ".join(
                f"string {string_number}, fret {fret}"
                for string_number, fret in candidates
            )
            prompt = (
                "Analyze this guitar performance frame. "
                "Return only JSON with this exact shape: "
                '{"visible":true|false,"string":1-6|null,"fret":0-24|null,'
                '"finger":"index|middle|ring|pinky|unknown","confidence":0.0-1.0}.\n'
                f"The detected audio pitch is MIDI {midi}. "
                f"Only choose one of these pitch-compatible positions: {candidate_text}. "
                "If the fretting finger, neck, and exact string/fret are not clearly visible, "
                "set visible=false, string=null, fret=null, finger=unknown, and confidence=0.0. "
                "Do not infer a position when it is occluded or unclear."
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=encoded.tobytes(), mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            text = getattr(response, "text", "").strip()
            data = json.loads(text)

            visible = bool(data.get("visible"))
            string_number = data.get("string")
            fret = data.get("fret")
            finger = str(data.get("finger", "unknown")).lower()
            confidence = float(data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))

            position = (string_number, fret)
            if (
                not visible
                or position not in candidates
                or finger not in {"index", "middle", "ring", "pinky", "unknown"}
                or confidence < 0.55
            ):
                return {
                    "visual_status": "gemini-uncertain",
                    "visual_confidence": round(confidence, 3),
                    "visual_string": None,
                    "visual_fret": None,
                    "finger": "unknown",
                    "gemini_answer": data,
                }

            return {
                "visual_status": "gemini-visible",
                "visual_confidence": round(confidence, 3),
                "visual_string": int(string_number),
                "visual_fret": int(fret),
                "finger": finger,
                "gemini_answer": data,
            }
        except Exception as error:
            logger.exception("Gemini frame analysis failed: %s", error)
            return self._unavailable()

    @staticmethod
    def _pitch_candidates(midi: int) -> list[tuple[int, int]]:
        standard_tuning = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}
        candidates = []
        for string_number, open_midi in standard_tuning.items():
            fret = midi - open_midi
            if 0 <= fret <= 24:
                candidates.append((string_number, fret))
        return candidates

    @staticmethod
    def _unavailable() -> dict:
        return {
            "visual_status": "unavailable",
            "visual_confidence": 0.0,
            "visual_string": None,
            "visual_fret": None,
            "finger": "unknown",
            "gemini_answer": None,
        }
