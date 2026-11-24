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
- Runtime files such as videos, WAV files, databases, and temporary files are outside feature source code.
- Features can later be moved into microservices because each feature is grouped and has its own service and repository boundaries.

Do not commit uploaded media, generated audio, databases, virtual environments, environment variables, or secrets.

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
- Python 3.11+
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
uv sync
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

Check API health:

```bash
curl http://127.0.0.1:8000/api/health
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

## Future processing stages

The upload stage is not transcription yet. Planned stages are:

1. `upload`: validate and store the video.
2. `media`: extract and normalize audio.
3. `transcription`: detect pitches and note timing.
4. `tab-generation`: map pitches to guitar strings and frets.
5. `chat`: answer questions using the source video, transcript, and generated tabs.

## API notes

- CORS currently allows the Vite development origins `http://localhost:5173` and `http://127.0.0.1:5173`.
- The upload API is under `POST /api/uploads`.
- The API health check is under `GET /api/health`.
- Uploaded files should be stored in object storage in production rather than only on a local server filesystem.
