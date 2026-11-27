from pathlib import Path

from basic_pitch.inference import predict
from basic_pitch.constants import CONTOURS_BINS_PER_SEMITONE


class TranscriptionError(RuntimeError):
    pass


class TranscriptionService:
    STANDARD_TUNING = {
        6: 40,
        5: 45,
        4: 50,
        3: 55,
        2: 59,
        1: 64,
    }

    def transcribe(self, audio_path: Path) -> list[dict]:
        if not audio_path.exists():
            raise TranscriptionError("Extracted WAV file was not found")

        try:
            _, _, note_events = predict(audio_path)
        except Exception as error:
            raise TranscriptionError("Basic Pitch could not process the audio") from error

        notes = []
        for start, end, midi, confidence, bend_data in note_events:
            midi_number = int(midi)
            guitar_position = self.map_to_guitar(midi_number)
            if guitar_position is None:
                continue

            string_number, fret = guitar_position
            notes.append(
                {
                    "pitch": self.midi_to_pitch(midi_number),
                    "midi": midi_number,
                    "string": string_number,
                    "fret": fret,
                    "start_seconds": round(float(start), 3),
                    "duration_seconds": round(max(float(end) - float(start), 0), 3),
                    "confidence": round(float(confidence), 3),
                    "bend_curve": [float(value) / CONTOURS_BINS_PER_SEMITONE for value in bend_data]
                    if bend_data is not None else [],
                }
            )

        return sorted(notes, key=lambda note: note["start_seconds"])

    def map_to_guitar(self, midi: int) -> tuple[int, int] | None:
        candidates = []
        for string_number, open_midi in self.STANDARD_TUNING.items():
            fret = midi - open_midi
            if 0 <= fret <= 24:
                candidates.append((fret, string_number))

        if not candidates:
            return None

        fret, string_number = min(candidates)
        return string_number, fret

    @staticmethod
    def midi_to_pitch(midi: int) -> str:
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        octave = midi // 12 - 1
        return f"{names[midi % 12]}{octave}"
