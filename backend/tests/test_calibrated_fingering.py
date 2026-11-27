import unittest
from types import SimpleNamespace

import numpy as np

from app.audio.fingering import HandPosition, optimize_fingering
from app.video.calibrated_vision import _annotate_note, _stable_hand_position
from app.video.finger_evidence import assign_fingers, score_fingers
from app.video.fretboard import Fretboard, FretboardCalibration, HandObservation


class CalibratedFingeringTests(unittest.TestCase):
    def test_same_pitch_moves_to_a_string_in_reach(self):
        note = dict(midi=71, string=1, fret=7, start_seconds=0, confidence=0.95)
        [selected] = optimize_fingering([note], [{}], [HandPosition(12)])
        self.assertEqual((selected["string"], selected["fret"]), (2, 12))
        self.assertEqual(selected["midi"], note["midi"])

    def test_fingertip_can_override_index_reach(self):
        note = dict(midi=71, string=1, fret=7, start_seconds=0, confidence=0.95)
        [selected] = optimize_fingering([note], [{(1, 7): 0.85}], [HandPosition(12)])
        self.assertEqual((selected["string"], selected["fret"]), (1, 7))

    def test_conflict_preserves_pitch_and_reports_uncertainty(self):
        note = dict(midi=47, string=6, fret=7, start_seconds=0, confidence=0.8)
        hand = HandPosition(12)
        [selected] = optimize_fingering([note], [{}], [hand])
        annotated = _annotate_note(note, selected, {}, hand)
        self.assertEqual(annotated["midi"], note["midi"])
        self.assertEqual(annotated["visual_status"], "calibrated-conflict")

    def test_open_string_remains_available(self):
        note = dict(midi=64, string=1, fret=0, start_seconds=0, confidence=0.95)
        [selected] = optimize_fingering([note], [{}], [HandPosition(12)])
        self.assertEqual((selected["string"], selected["fret"]), (1, 0))

    def test_hand_position_uses_agreement_and_ignores_outliers(self):
        self.assertIsNone(_stable_hand_position([HandPosition(8), HandPosition(12)]))
        hand = _stable_hand_position([HandPosition(12), HandPosition(12.4), HandPosition(8)])
        self.assertTrue(hand.from_index)
        self.assertAlmostEqual(hand.anchor_fret, 12.2)
        hand = _stable_hand_position([HandPosition(12), HandPosition(12.4, from_index=False)])
        self.assertFalse(hand.from_index)

    def test_visible_fingertips_override_a_crossed_index(self):
        calibration = FretboardCalibration(
            reference_fret=24,
            points=[{"x": x, "y": y} for x, y in [(0, 0), (0, 1), (1, 1), (1, 0)]],
        )
        board = Fretboard(calibration)
        hand = [SimpleNamespace(x=0, y=0) for _ in range(21)]
        for landmark, fret in zip((8, 12, 16, 20), (12, 11, 9, 8)):
            hand[landmark] = SimpleNamespace(x=board._contact_x(fret), y=0.4)
        observation = board.observe_hands([hand])
        self.assertFalse(observation.position.from_index)
        self.assertAlmostEqual(observation.position.anchor_fret, 8, places=5)
        self.assertIsNone(board.observe_hands([hand, hand]).position)

    def test_middle_finger_approaches_d13_from_the_index_on_g12(self):
        frames = [
            HandObservation(np.empty((0, 2)), fingers=((12, 3), (13.6, 2.9), None, None)),
            HandObservation(np.empty((0, 2)), fingers=((12, 3), (13.05, 2), None, None)),
        ]
        scores = score_fingers(63, frames, HandPosition(12))
        note = dict(midi=63, string=4, fret=13, start_seconds=0)
        self.assertEqual(assign_fingers([note], [scores]), ["middle"])
        self.assertEqual(score_fingers(63, frames[:1], HandPosition(12)), {})

    def test_fingertip_in_bass_zone_cannot_support_a_treble_candidate(self):
        frame = HandObservation(np.empty((0, 2)), fingers=(None, (8, 0.4), None, None))
        self.assertNotIn((3, 8), score_fingers(63, [frame, frame], None))

    def test_finger_evidence_helps_rank_pitch_compatible_positions(self):
        note = dict(midi=64, string=2, fret=5, start_seconds=0, confidence=1)
        positional_evidence = [{(2, 5): 0.30, (3, 9): 0.72}]
        [before] = optimize_fingering([note], positional_evidence, [HandPosition(5)])
        [after] = optimize_fingering([note], positional_evidence, [HandPosition(5)], [{(3, 9): 0.9}])
        self.assertEqual((before["string"], before["fret"]), (2, 5))
        self.assertEqual((after["string"], after["fret"]), (3, 9))

    def test_same_finger_at_different_frets_in_chord_is_ambiguous(self):
        notes = [dict(string=3, fret=12, start_seconds=0), dict(string=4, fret=13, start_seconds=0.01)]
        scores = [{(3, 12): {"middle": 0.8}}, {(4, 13): {"middle": 0.8}}]
        self.assertEqual(assign_fingers(notes, scores), ["unknown", "unknown"])
