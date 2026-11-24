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
5. Uses FFmpeg to extract the audio and create a WAV file.
6. Stores job metadata and file paths in `backend/data/videos.sqlite3`.
7. Returns metadata to the frontend.

## What WAV is

WAV is an audio file format. It stores sampled audio as waveform data. A WAV file is not video and normally does not contain the visual frames from a guitar performance.

WAV is useful for transcription because it is widely supported and provides a simple, uncompressed representation of sound. The current file is also converted to:

- **PCM 16-bit samples:** stores each audio sample as signed 16-bit data.
- **Mono:** combines or selects one channel instead of keeping separate left and right channels.
- **44.1 kHz:** captures 44,100 samples per second.

### Why FFmpeg is used

FFmpeg separates the audio from the uploaded video and performs format conversion. ffprobe is the metadata-reading companion to FFmpeg.

The extraction command used by the backend is conceptually:

```bash
ffmpeg -i input.mp4 -vn -ac 1 -ar 44100 -acodec pcm_s16le output.wav
```

The command means:

- `-i input.mp4`: read the uploaded video.
- `-vn`: discard video frames; produce audio only.
- `-ac 1`: convert the audio to mono.
- `-ar 44100`: resample the audio to 44.1 kHz.
- `-acodec pcm_s16le`: encode uncompressed signed 16-bit PCM audio.
- `output.wav`: write the extracted audio file.

Metadata is obtained with ffprobe and can include duration, resolution, and frame rate.

### Why mono 44.1 kHz is used

A guitar video may contain stereo audio, but for the initial pitch-transcription version, mono is simpler and usually sufficient because the model must identify pitches from sound rather than preserve a stereo mix.

44.1 kHz is a common audio format for music and is a useful balance between detail and processing size. A 60-second, mono, 44.1 kHz, 16-bit WAV contains 60 × 44,100 × 2 bytes of waveform data, approximately 5.3 MB for the audio itself.

Mono and stereo audio can differ in spatial information, such as where a player or instrument appears in a recording. That extra information is not normally needed for note transcription. Stereo separation may be useful later for source separation or more complex recordings.

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

Basic Pitch is installed in `backend/.venv` under Python 3.11.
The verified macOS dependency set includes `setuptools<81` and `scikit-learn==1.5.1`.
Python 3.12 failed because the Basic Pitch dependency chain resolves to a TensorFlow macOS wheel that only supports Python 3.11.

The backend provides:

- `POST /api/transcriptions/{job_id}`: generate and save transcription notes.
- `GET /api/transcriptions/{job_id}`: retrieve a saved transcription.

The service reads the uploaded WAV from SQLite job metadata, calls Basic Pitch, maps each detected MIDI pitch to the first valid position in standard tuning, and stores the resulting JSON in SQLite.

### MVP model choice

Basic Pitch is a suitable baseline because it:

- Accepts an audio file or waveform and detects notes and timing.
- Returns MIDI-like note events and confidence values.
- Supports polyphonic music, including chords.
- Runs locally, avoiding a transcription API dependency during development.
- Produces a useful baseline for short, clean guitar recordings.

Basic Pitch is a pitch detector, not a complete guitar-to-tab converter. The backend must still:

1. Read the extracted mono 44.1 kHz WAV.
2. Run Basic Pitch to detect note pitches and time ranges.
3. Choose a plausible guitar-string and fret position for each pitch.
4. Measure beats or tempo and group notes into measures.
5. Return structured JSON for React to render as tabs.

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

The backend owns pitch detection and tab mapping. The frontend receives JSON and only renders it.

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

## Alternative approaches to evaluate later

- **Crepe:** useful for monophonic pitch tracking, but less suitable for complete chord detection.
- **Demucs:** can separate instruments or isolate a guitar in mixed recordings before transcription.
- **A specialized transcription model:** suitable when Basic Pitch accuracy is insufficient for a specific guitar style.
- **A commercial transcription API:** faster to prototype with but should be isolated behind a backend adapter so it can be replaced.

Do not use Docling for transcription. Docling processes documents; it does not convert guitar audio to notes.

## API notes

- CORS currently allows the Vite development origins `http://localhost:5173` and `http://127.0.0.1:5173`.
- The upload API is under `POST /api/uploads`.
- The API health check is under `GET /api/health`.
- Uploaded files should be stored in object storage in production rather than only on a local server filesystem.
