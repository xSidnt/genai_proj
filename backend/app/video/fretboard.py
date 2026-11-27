from dataclasses import dataclass

import cv2
import numpy as np
from pydantic import BaseModel, Field, model_validator

from app.audio.fingering import FretEvidence, HandPosition
from app.audio.notes import TranscriptionService


class ImagePoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class FretboardCalibration(BaseModel):
    start_fret: int = Field(default=0, ge=0, le=23)
    reference_fret: int = Field(ge=2, le=24)
    reference_seconds: float | None = Field(default=None, ge=0)
    # Low E at start wire, high E at start wire, high E at end wire, low E at end wire.
    points: tuple[ImagePoint, ImagePoint, ImagePoint, ImagePoint]

    def image_points(self) -> np.ndarray:
        return np.float32([(point.x, point.y) for point in self.points])

    @model_validator(mode="after")
    def validate_quad(self):
        if self.start_fret >= self.reference_fret:
            raise ValueError("Choose a higher-numbered fret for the end wire")
        points = self.image_points()
        if not cv2.isContourConvex(points) or cv2.contourArea(points) < 0.0001:
            raise ValueError("Mark four distinct fretboard corners in the displayed order")
        return self


@dataclass(frozen=True)
class HandObservation:
    fingertips: np.ndarray
    position: HandPosition | None = None


class Fretboard:
    def __init__(self, calibration: FretboardCalibration) -> None:
        self.image_points = calibration.image_points()
        self.reference_seconds = calibration.reference_seconds
        self.transform = self._transform(self.image_points)
        self.start_fret = calibration.start_fret
        self.reference_fret = calibration.reference_fret
        start_distance = 1 - 2 ** (-self.start_fret / 12)
        span = (1 - 2 ** (-self.reference_fret / 12)) - start_distance
        self.wires = {
            fret: ((1 - 2 ** (-fret / 12)) - start_distance) / span
            for fret in range(self.start_fret, self.reference_fret + 1)
        }
        frets = list(range(self.start_fret + 1, self.reference_fret + 1))
        self.contact_frets = [self.start_fret, *frets, self.reference_fret + 0.25]
        self.contact_positions = [0.0, *(self._contact_x(fret) for fret in frets), 1.0]

    @staticmethod
    def _transform(corners: np.ndarray) -> np.ndarray:
        return cv2.getPerspectiveTransform(corners, np.float32([(0, 0), (0, 5), (1, 5), (1, 0)]))

    def observe_hands(self, hands, corners: np.ndarray | None = None) -> HandObservation:
        tips = [[(hand[index].x, hand[index].y) for index in (8, 12, 16, 20)] for hand in hands]
        if not tips:
            return HandObservation(np.empty((0, 2), dtype=np.float32))
        transform = self.transform if corners is None else self._transform(corners)
        projected = cv2.perspectiveTransform(np.float32(tips), transform)
        x, y = projected[..., 0], projected[..., 1]
        near_strings = (x >= 0) & (x <= 1) & (y >= -0.5) & (y <= 5.5)
        active_hands = np.flatnonzero(near_strings.any(axis=1))
        position = None
        # Two hands on the neck can tap beyond the fretting hand's reach.
        if len(active_hands) == 1:
            hand = active_hands[0]
            lowest_fret = self._fret_at(float(x[hand, near_strings[hand]].min()))
            index_x, index_y = projected[hand, 0]
            if 0 <= index_x <= 1 and -0.65 <= index_y <= 6.1:
                index_fret = self._fret_at(float(index_x))
                if index_fret <= lowest_fret + 1.0:
                    position = HandPosition(index_fret)
            # A lifted or crossed index can give a poor estimate of the reachable frets.
            if position is None and near_strings[hand].sum() >= 2:
                position = HandPosition(lowest_fret, from_index=False)
        return HandObservation(projected[near_strings], position)

    def _fret_at(self, x: float) -> float:
        return float(np.interp(x, self.contact_positions, self.contact_frets))

    def _contact_x(self, fret: int) -> float:
        wire = self.wires[fret]
        # A fretting finger presses slightly on the nut side of the fret wire.
        return wire - 0.25 * (wire - self.wires[fret - 1])

    def score_pitch(self, midi: int, fingertips: np.ndarray) -> FretEvidence:
        if not len(fingertips):
            return {}

        scores = {}
        for string, open_midi in TranscriptionService.STANDARD_TUNING.items():
            fret = midi - open_midi
            if not self.start_fret < fret <= self.reference_fret:
                continue
            wire = self.wires[fret]
            width = wire - self.wires[fret - 1]
            x_distance = abs(fingertips[:, 0] - self._contact_x(fret)) / width
            y_distance = abs(fingertips[:, 1] - (6 - string))
            fret_proximity = np.maximum(0, 1 - x_distance / 0.85)
            string_proximity = np.maximum(0, 1 - y_distance / 0.9)
            score = float((fret_proximity * (0.25 + 0.75 * string_proximity)).max())
            if score > 0:
                scores[(string, fret)] = score

        return scores
