from pathlib import Path


class GuitarSeparationError(RuntimeError):
    pass


class GuitarSeparationService:
    MODEL_NAME = "htdemucs_6s"
    DEVICE = "cpu"

    def separate_guitar(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.is_file():
            raise GuitarSeparationError("Input WAV file was not found")

        try:
            from demucs.api import Separator, save_audio

            separator = Separator(
                model=self.MODEL_NAME,
                device=self.DEVICE,
                shifts=1,
                progress=False,
            )
            _original, stems = separator.separate_audio_file(input_path)
        except Exception as error:
            raise GuitarSeparationError("Demucs could not separate the guitar stem") from error

        guitar_stem = stems.get("guitar")
        if guitar_stem is None:
            raise GuitarSeparationError(
                f"Demucs model {self.MODEL_NAME} did not return a guitar stem"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            save_audio(
                guitar_stem,
                output_path,
                samplerate=separator.samplerate,
                clip="rescale",
                bits_per_sample=16,
            )
        except Exception as error:
            raise GuitarSeparationError("Could not save the separated guitar audio") from error

        return output_path
