# Riffroom

Riffroom is a modular monolith for turning short guitar videos into guitar tabs and providing AI-assisted explanations of the detected music.

## Product goal

The current MVP allows a user to upload a 30-second to 60-second guitar video, preview it in the React frontend, send it to the backend, validate it, extract media metadata, and convert the video's audio into a format suitable for transcription.

The future transcription pipeline will:

1. Detect notes and their timings in the extracted audio.
2. Estimate pitches and convert them to frets and guitar strings.
3. Generate playable tablature.
4. Let the user ask questions about the result through an AI chat panel.

## Architecture

```text
genai_proj/
├── frontend/                 # React + TypeScript + Vite
├── backend/
│   ├── app/
│   │   ├── upload/           # Upload API, service, repository, and models
│   │   └── main.py           # FastAPI application composition
│   ├── data/                 # SQLite database and application state
│   ├── storage/
│   │   ├── uploads/          # Original uploaded videos
│   │   ├── audio/            # Extracted WAV audio files
│   │   └── tmp/              # Temporary processing files
│   ├── tests/                # Backend tests
│   ├── pyproject.toml
│   └── uv.lock
└── README.md
```

This is a modular monolith:

- The frontend and backend are separate applications inside one repository.
- Backend features own their API route, business logic, data models, and persistence access.
- Runtime files such as videos, WAV files, databases, virtual environments, environment variables, or secrets.

## Tech stack

### Frontend

- React
- TypeScript
- Vite
- npm
- Lucide React
- ESLint

### Backend

- Python
- FastAPI
- Pydantic
- SQLite
- FFmpeg
- ffprobe
- Demucs (`htdemucs_6s` guitar stem)
- Basic Pitch
- uv

## Requirements

- Node.js and npm
- Python 3.11 (required for the current macOS Basic Pitch dependencies)
- FFmpeg and ffprobe
- uv

Install FFmpeg on macOS with:

```bash
brew install ffmpeg uv
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Build and validate the frontend with:

```bash
cd frontend
npm run build
npm run lint
```

## Backend setup

```bash
cd backend
uv python install 3.11
uv venv --python 3.11 --clear .venv
uv sync
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

Check API health:

```bash
curl http://127.0.0.1:8000/api/health
```

Create a transcription for an uploaded job:

```bash
curl -X POST http://127.0.0.1:8000/api/transcriptions/JOB_ID
```

Retrieve an existing transcription:

```bash
curl http://127.0.0.1:8000/api/transcriptions/JOB_ID
```

## Current upload behavior

The upload endpoint accepts:

- MP4
- MOV
- WebM
- Maximum file size: 100 MB
- Maximum duration: 60 seconds

The frontend sends a video using `multipart/form-data`. The endpoint currently performs these steps:

1. Validates the file extension.
2. Stores the original upload under `backend/storage/uploads/<job-id>/`.
3. Uses ffprobe to determine duration, width, height, and frame rate.
4. Rejects videos longer than 60 seconds.
5. Uses FFmpeg to extract stereo 44.1 kHz PCM WAV audio (two channels are retained for source separation).
6. Stores job metadata and file paths in `backend/data/videos.sqlite3`.
7. Returns metadata to the frontend.

## What WAV is

WAV is an audio file format. It stores sampled audio as waveform data. A WAV file is not video and normally does not contain the visual frames from a guitar performance.

WAV is useful for transcription because it is widely supported and provides a simple, uncompressed representation of sound. The current file is also converted to:

- **PCM 16-bit samples:** stores each audio sample as signed 16-bit data.
- **Stereo:** preserves left and right channels because Demucs source separation benefits from the original stereo mix. If the uploaded video is mono, FFmpeg duplicates the mono channel to both sides.
- **44.1 kHz:** captures 44,100 samples per second.

### Why FFmpeg is used

FFmpeg separates the audio from the uploaded video and performs format conversion. ffprobe is the metadata-reading companion to FFmpeg.

The extraction command used by the backend is conceptually:

```bash
ffmpeg -i input.mp4 -vn -ac 2 -ar 44100 -acodec pcm_s16le output.wav
```

The command means:

- `-i input.mp4`: read the uploaded video.
- `-vn`: discard video frames; produce audio only.
- `-ac 2`: output two channels for source separation.
- `-ar 44100`: resample the audio to 44.1 kHz.
- `-acodec pcm_s16le`: encode uncompressed signed 16-bit PCM audio.
- `output.wav`: write the extracted audio file.

Metadata is obtained with ffprobe and can include duration, resolution, and frame rate.

### Why stereo 44.1 kHz is used

A stereo mix retains spatial cues that can help source-separation models. The transcription model can downmix the isolated guitar stem when it analyzes pitch.

44.1 kHz is a common audio format for music and a useful balance between detail and processing size. A 60-second, stereo, 44.1 kHz, 16-bit WAV contains 60 × 44,100 × 2 channels × 2 bytes, approximately 10.6 MB for the audio itself.

The stereo audio is used as input to Demucs. Basic Pitch receives Demucs' isolated guitar stem when available; the current pipeline falls back to the original stereo mix if separation fails.

## How the frontend understands the upload

The website does not directly analyze FFmpeg's WAV output. The React frontend uploads the original video and displays the return value from the backend.

The frontend uses:

- `FormData` to place the file in a `multipart/form-data` HTTP request.
- `fetch` to call `POST /api/uploads`.
- `URL.createObjectURL()` to create a temporary browser preview URL for the original video.
- The JSON response to display duration, width, height, and frame rate.

The upload endpoint returns metadata similar to:

```json
{
  "job_id": "unique-job-id",
  "status": "ready",
  "duration_seconds": 42,
  "width": 1920,
  "height": 1080,
  "frame_rate": 30,
  "video_path": "backend/storage/uploads/unique-job-id/source.mp4",
  "audio_path": "backend/storage/audio/unique-job-id/audio.wav"
}
```

The browser does not need to understand WAV internals. Python processes the WAV through FFmpeg and later through a transcription model.

## Docling and transcription

Docling is not used for this feature. It is designed to extract structured information from documents such as PDFs, Word documents, and presentations.

The WAV is intended for a music/audio transcription model instead. A first implementation may use an open-source pitch or transcription model such as Basic Pitch, followed by logic that converts detected notes and timings into guitar strings and frets.

The website will understand tab information only after the backend converts audio features into a structured JSON transcription containing values such as:

```json
{
  "notes": [
    { "pitch": "E2", "string": 6, "fret": 0, "start_seconds": 0.25, "duration_seconds": 0.50 }
  ]
}
```

That JSON can be rendered in React as tablature and then used as context for the AI chat feature.

## Transcription strategy

### Implemented MVP model: Basic Pitch

Basic Pitch and Demucs are installed in `backend/.venv` under Python 3.11.
The verified macOS dependency set includes `setuptools<81` and `scikit-learn==1.5.1`.
Python 3.12 failed because the Basic Pitch dependency chain resolves to a TensorFlow macOS wheel that only supports Python 3.11.
The project also pins `numpy<2` because the selected PyTorch wheel is not compatible with NumPy 2.

The backend provides:

- `POST /api/transcriptions/{job_id}`: generate and save transcription notes.
- `GET /api/transcriptions/{job_id}`: retrieve a saved transcription.

The service reads the uploaded stereo WAV from SQLite job metadata, runs Demucs `htdemucs_6s` to isolate its `guitar` stem, passes that stem to Basic Pitch, maps each detected MIDI pitch to a standard-tuning string/fret, and stores the resulting JSON in SQLite. If separation fails, it logs the failure and runs Basic Pitch on the original mix. The response's `audio_source` field indicates `demucs_guitar`, `original_fallback`, or `original` for a legacy result.

On first transcription, Demucs downloads its pretrained model weights. Separation currently runs on CPU and can take longer than the clip duration. The model weights are cached outside the repository by the model library; generated `guitar.wav` stems are stored under `backend/storage/audio/<job-id>/`.

### MVP model choice

Basic Pitch is a suitable baseline because it:

- Accepts an audio file or waveform and detects notes and timing.
- Returns MIDI-like note events and confidence values.
- Supports polyphonic music, including chords.
- Runs locally, avoiding a transcription API dependency during development.
- Produces a useful baseline for short, clean guitar recordings.

Basic Pitch is a pitch detector, not a complete guitar-to-tab converter. The backend must still:

1. Read the extracted stereo 44.1 kHz WAV.
2. Run Demucs `htdemucs_6s` and save its `guitar` stem to `backend/storage/audio/<job-id>/guitar.wav`.
3. Run Basic Pitch on the guitar stem to detect note pitches and time ranges.
4. Choose a plausible guitar-string and fret position for each pitch.
5. Measure beats or tempo and group notes into measures.
6. Return structured JSON for React to render as tabs.

Demucs is a preprocessing step, not a guarantee of clean guitar isolation. Its six-stem model adds guitar and piano stems, and the upstream repository describes guitar quality as usable but subject to bleeding and artifacts. The project currently runs separation on CPU. Demucs' upstream repository is archived, so treat this as an experiment and measure its results on our own clips before making it a production dependency.

An initial three-second excerpt check on one uploaded clip produced 21 Basic Pitch events from the original mix versus 1 event from the Demucs guitar stem (only 4 original events were at confidence ≥0.6). This is a useful smoke-test observation, not an accuracy benchmark: a short segment and one clip are not enough to conclude that Demucs improves all recordings.

### MVP processing stages

The processing pipeline is:

1. `upload`: validate and store the video.
2. `media`: extract and normalize the audio.
3. `transcription`: detect pitches and note timing with Basic Pitch.
4. `tab-generation`: map pitches to guitar strings and frets.
5. `chat`: answer questions using the source video, transcript, and generated tabs.

### Suggested transcription result

Basic Pitch can be converted into an application-owned format rather than passed directly to React:

```json
{
  "job_id": "unique-job-id",
  "status": "ready",
  "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
  "tempo_bpm": null,
  "notes": [
    {
      "pitch": "E2",
      "midi": 40,
      "string": 6,
      "fret": 0,
      "start_seconds": 0.25,
      "duration_seconds": 0.50,
      "confidence": 0.92
    }
  ]
}
```

The backend owns pitch detection and maps each detected MIDI pitch to a standard-tuning string and fret. The frontend receives the resulting JSON and renders a six-line tablature staff in `frontend/src/components/GuitarTabStaff.tsx`.

The current staff:

- Places each detected fret number on its mapped string.
- Positions notes horizontally by their detected start time.
- Shows second markers on a ruler and supports horizontal scrolling.
- Displays all model events, including low-confidence detections; note confidence affects marker opacity and is available on hover.
- Does not yet quantize notes to beats, draw measure bars, infer tempo, or optimize a whole phrase for comfortable fingering.

This is a working visual prototype of the model output, not yet polished or musically corrected tablature.

### MVP limitations

Basic Pitch is a starting point, not a guaranteed transcription engine.

Expected limitations include:

- Chords and fast passages may be detected imprecisely.
- A pitch alone can correspond to multiple fret positions.
- Timing estimates can drift without a clear beat or metronome.
- String selection may need playability scoring rather than one fixed rule.
- Finger noise, room noise, effects, and poor lighting can reduce quality.
- Notes played outside standard tuning require tuning detection or user input.

The transcription endpoint should use an asynchronous job. Processing should not block the upload request because audio models are slower than FFmpeg extraction.

### Observed accuracy issue and next iteration

In the first real-video check, Basic Pitch returned many notes during the opening seconds when the visible guitarist was not yet playing (there may be background guitar/audio). The current implementation displays all detections and does not identify which audible instrument belongs to the visible performer. This is expected to be a model/source-selection limitation, not a tablature-rendering issue.

The current tab output is not expected to match the performance reliably yet. Basic Pitch detects pitches from the complete audio mix; the current tab mapper then independently chooses the lowest-fret standard-tuning position for each pitch. It does not use the player's visible hand position, and the current renderer has no beat quantization. It can therefore show background notes, choose a different valid string/fret than the performer used, or place notes at imprecise times.

Recommended next steps, in order:

1. Keep the raw model output for debugging, but add an adjustable confidence threshold and test stricter Basic Pitch onset/frame thresholds against real guitar clips. Do not assume thresholding alone identifies the foreground guitarist.
2. Add user-selectable start/end points for the section to transcribe. The user can exclude an intro or background-only section using the video preview; FFmpeg should trim the extracted audio to that range before inference, and returned note times should be offset back to the full-video timeline.
3. Evaluate separated audio or a guitar-focused transcription model on clips where background music overlaps the performance. General source-separation stems are not guaranteed to isolate guitar from every mix.
4. Build a small evaluation set with labeled examples for silence/background-only, single-note playing, chords, and noisy recordings. Compare false detections and missed notes before tuning the model further.
5. After note detections are reasonably reliable, improve fret-position continuity and add beat/measure quantization. Better tab rendering cannot correct incorrect pitch detections.

### Vision-assisted guitar analysis

A vision model can complement audio transcription, but a general video/vision-language model should not be expected to read exact strings and frets reliably. Fretboard details are small, fingers occlude strings, and camera perspective/resolution vary.

Recommended hybrid design:

1. Preserve audio/video timestamps when decoding. A coarse video pass (for example, a few frames per second) finds likely playing regions, checks that the neck and hands are visible, and lets the user exclude intros or background-only parts.
2. Run source separation and audio transcription only on the chosen region. Audio provides note pitches, onset times, durations, and possible chord groups.
3. For each audio note/chord onset, inspect nearby source frames at the original frame resolution. A fixed frame every 0.5 seconds is useful for coarse activity but can miss fast notes; use audio event timestamps to trigger the detailed visual check.
4. Detect the guitar neck, string lines, fret boundaries, and fretting-hand/fingertip landmarks. Calibrate/project the fretboard geometry into image coordinates, then estimate which string/fret each fingertip presses. Use audio pitch plus tuning to rule out visually plausible but acoustically impossible candidates.
5. Track candidates across time, preferring a coherent hand position and plausible transitions. Return visual, audio, and combined confidence separately; retain low-confidence notes for user review/correction.

Possible implementation pieces include an object detector for guitar/neck regions, a hand-landmark model for finger locations, and OpenCV geometry for strings/fret boundaries. A general multimodal vision model can help with coarse activity or visibility judgments, but exact fretboard localization should be evaluated with a purpose-built CV pipeline. Camera angle, motion blur, low resolution, and fingers covering strings can make exact detection impossible for some clips.

Detecting **which finger** (index/middle/ring/pinky) is pressing is possible only when the hand is large and clear enough, and is harder than detecting the string/fret. Finger identity is not required to write a tab; it is an optional later feature for fingering suggestions. Do not invent a finger label when the image is occluded—return unknown/low confidence.

Jev is not part of pixel/frame analysis. A vision pipeline would first turn frames into structured observations (for example, candidate fret positions, hand visibility, and confidence). Jev could then classify or score those text/structured candidates against a predefined schema, if evaluation shows it helps. It cannot itself find notes, strings, frets, or fingers from a video frame.

### Recommended milestones

1. **Make audio events trustworthy:** compare the original mix and Demucs guitar stem, add a user-selectable analysis range and confidence controls, and evaluate against a few labeled clips.
2. **Add video-assisted region selection:** show coarse “playing likely / uncertain” time ranges and let the user confirm the region before transcription.
3. **Prototype visual fretboard localization:** start with a short, close, well-lit clip; detect the neck/strings/frets and hand landmarks; overlay candidate positions for manual verification.
4. **Fuse candidates:** match detected audio pitches to feasible visible string/fret positions, with continuity and confidence, and allow correction.
5. **Add finger guidance only after fret/string accuracy is measured.**

Example outputs for a vision pass could include `playing_visible`, `fretting_hand_visible`, `picking_hand_active`, `neck_visible`, and a confidence score, all tied to a video timestamp. A later Jev call could classify a structured text representation of these signals or rank a finite set of already-generated candidates. Jev cannot receive the image pixels itself.

A Gemini-class multimodal model is appropriate for coarse questions such as “does the person appear to be playing during this time range?” or for helping a user mark the performance region. It is not the first choice for frame-accurate note transcription or exact fret/string classification. Use selected frames with timestamps rather than asking a general model to generate a full tab from the whole clip. The proposed sample rates are starting points to evaluate, not fixed requirements; adjust for the clip's frame rate and note speed.

**Jev is different from a vision-language model.** TypeSafe describes Jev as a structured classification/decision model: it receives text plus questions and returns predefined outputs such as yes/no, a choice, or a score with probabilities. It does not accept raw video frames or images, and it does not generate free-form text. Jev could potentially classify text features produced by a separate vision/audio pipeline (for example, activity labels and timestamps), but it cannot itself inspect the guitar video. Verify current modalities and API details against the [TypeSafe Jev announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev) and [TypeSafe documentation](https://docs.typesafe.ai/introduction).

## Alternative approaches to evaluate later

- **Crepe:** useful for monophonic pitch tracking, but less suitable for complete chord detection.
- **Demucs:** currently integrated as an experimental guitar-stem preprocessing step. The upstream repository is archived; the six-stem model's guitar output can have bleed and artifacts, so compare on an evaluation set before relying on it.
- **A specialized transcription model:** suitable when Basic Pitch accuracy is insufficient for a specific guitar style.
- **A commercial transcription API:** faster to prototype with but should be isolated behind a backend adapter so it can be replaced.

Do not use Docling for transcription. Docling processes documents; it does not convert guitar audio to notes.

## API notes

- CORS currently allows the Vite development origins `http://localhost:5173` and `http://127.0.0.1:5173`.
- The upload API is under `POST /api/uploads`.
- The API health check is under `GET /api/health`.
- Uploaded files should be stored in object storage in production rather than only on a local server filesystem.

## Tablature workspace and playback

The tablature panel takes roughly 55% of the desktop workspace; the video and chat panels retain narrower columns. The tab staff is divided into compact eight-second timeline rows rather than one long horizontal strip. Each row has its own time ruler, and the red playhead appears in the row matching the video's current playback/seek position. Scroll vertically for additional rows; horizontal scrolling remains available at narrower widths. These are time windows, not musical measures, because tempo and beat quantization are not implemented yet.

## Implemented multimodal analysis workflow

The current application supports an explicit analysis range:

1. Upload a video and select a start/end section in the source panel.
2. Click **Analyze selected range**.
3. FFmpeg trims the extracted stereo audio to that range.
4. Demucs can separate a guitar stem, with fallback to the trimmed original audio.
5. Basic Pitch detects notes in the trimmed segment.
6. Detected timestamps are offset back onto the full-video timeline.
7. MediaPipe analyzes frames near note onsets and coarse frames every 0.5 seconds.
8. Jev-Vision can classify pitch-compatible string/fret candidates at each detected note frame.
9. The API returns audio, visual, and combined confidence fields, coarse hand/neck observations, Jev choices, probabilities, and answer mass.

Jev-Vision is optional and lazy-loaded on Apple Silicon through MPS. Set `JEV_VISION_ENABLED=false` to disable it. It receives no more than the six standard-tuning candidates compatible with each detected MIDI pitch plus a no-visible-candidate option. A visual position overrides the Basic Pitch string/fret mapping only when Jev confidence and answer mass meet thresholds. Otherwise the original mapping remains in place and uncertainty is reported.

The vision pass reports hand visibility, fretting-hand plausibility, neck-edge visibility, and visual confidence. Exact fret/string accuracy still requires real labeled guitar-frame evaluation and is not guaranteed by a general VQA-style checkpoint.

Results are cached by `(job_id, start_seconds, end_seconds)` in SQLite. The original video and extracted WAV remain stored for frame analysis and evaluation.

Gemini cloud vision is optional and activates when `GEMINI_API_KEY` is set in `backend/.env`. Copy `backend/.env.example`, add the key, and optionally set `GEMINI_MODEL` (default: `gemini-2.5-flash-lite`). Gemini receives a frame, detected MIDI pitch, and pitch-compatible string/fret candidates; it returns strict JSON including optional finger identity and confidence. If no key is configured or Gemini fails, MediaPipe/Jev remain as fallbacks.
