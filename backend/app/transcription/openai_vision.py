import base64
import json
import logging
import os
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class OpenAIVisionService:
    DEFAULT_MODEL = "gpt-6-luna"

    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        load_dotenv(backend_dir / ".env")
        load_dotenv(backend_dir.parent / ".env")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL)
        self.enabled = bool(self.api_key)
        self.client = None

    def infer_position(self, frame: np.ndarray | None, midi: int) -> dict:
        if frame is None or not self.enabled:
            return self._unavailable()

        candidates = self._pitch_candidates(midi)
        if not candidates:
            return self._unavailable()

        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            return self._unavailable()

        candidate_text = ", ".join(
            f"string {string_number}, fret {fret}"
            for string_number, fret in candidates
        )
        prompt = (
            "Analyze this guitar performance frame. Return only JSON with this exact shape: "
            '{"visible":true|false,"string":1-6|null,"fret":0-24|null,'
            '"finger":"index|middle|ring|pinky|unknown","confidence":0.0-1.0}. '
            f"The detected audio pitch is MIDI {midi}. Only choose from: {candidate_text}. "
            "If the neck, fretting finger, string, or fret is unclear, set visible=false, "
            "string=null, fret=null, finger=unknown, and confidence=0.0."
        )

        try:
            from openai import OpenAI

            if self.client is None:
                self.client = OpenAI(api_key=self.api_key)

            response = self.client.responses.create(
                model=self.model,
                text={"format": {"type": "json_object"}},
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")},
                    ],
                }],
            )
            data = json.loads(response.output_text)

            visible = bool(data.get("visible"))
            string_number = data.get("string")
            fret = data.get("fret")
            finger = str(data.get("finger", "unknown")).lower()
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))

            if (
                not visible
                or (string_number, fret) not in candidates
                or finger not in {"index", "middle", "ring", "pinky", "unknown"}
                or confidence < 0.55
            ):
                return {
                    "visual_status": "openai-uncertain",
                    "visual_confidence": round(confidence, 3),
                    "visual_string": None,
                    "visual_fret": None,
                    "finger": "unknown",
                    "openai_answer": data,
                }

            return {
                "visual_status": "openai-visible",
                "visual_confidence": round(confidence, 3),
                "visual_string": int(string_number),
                "visual_fret": int(fret),
                "finger": finger,
                "openai_answer": data,
            }
        except Exception as error:
            logger.exception("OpenAI frame analysis failed: %s", error)
            return self._unavailable()

    @staticmethod
    def _pitch_candidates(midi: int) -> list[tuple[int, int]]:
        standard_tuning = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}
        return [
            (string_number, midi - open_midi)
            for string_number, open_midi in standard_tuning.items()
            if 0 <= midi - open_midi <= 24
        ]

    @staticmethod
    def _unavailable() -> dict:
        return {
            "visual_status": "unavailable",
            "visual_confidence": 0.0,
            "visual_string": None,
            "visual_fret": None,
            "finger": "unknown",
            "openai_answer": None,
        }
