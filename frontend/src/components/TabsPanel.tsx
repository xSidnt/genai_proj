import { useState } from 'react'
import GuitarTabStaff from './GuitarTabStaff'

interface TabNote {
  pitch: string
  midi: number
  string: number
  fret: number
  start_seconds: number
  duration_seconds: number
  confidence: number
  visual_status?: string
  visual_confidence?: number
  combined_confidence?: number
  visual_string?: number
  visual_fret?: number
}

interface VideoObservation {
  timestamp_seconds: number
  hands_visible: number
  fretting_hand_visible: boolean
  neck_visible: boolean
  visual_confidence: number
}

interface TranscriptionResult {
  job_id: string
  status: string
  tuning: string[]
  tempo_bpm: number | null
  notes: TabNote[]
  audio_source: string
  start_seconds: number
  end_seconds: number
  video_observations: VideoObservation[]
}

interface TranscriptionErrorState {
  jobId: string
  message: string
}

interface TabsPanelProps {
  jobId: string | null
  playbackTime: number
  videoDuration: number
  startSeconds: number
  endSeconds: number
}

export default function TabsPanel({
  jobId,
  playbackTime,
  videoDuration,
  startSeconds,
  endSeconds,
}: TabsPanelProps) {
  const [transcription, setTranscription] = useState<TranscriptionResult | null>(null)
  const [transcriptionError, setTranscriptionError] = useState<TranscriptionErrorState | null>(null)
  const [isTranscribing, setIsTranscribing] = useState(false)

  const transcribeSelectedRange = async () => {
    if (!jobId || endSeconds <= startSeconds) return
    const activeJobId = jobId
    setIsTranscribing(true)
    setTranscriptionError(null)

    try {
      const params = new URLSearchParams({
        start_seconds: startSeconds.toFixed(3),
        end_seconds: endSeconds.toFixed(3),
      })
      const response = await fetch(
        `http://127.0.0.1:8000/api/transcriptions/${activeJobId}?${params}`,
        { method: 'POST' },
      )
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result.detail || 'Transcription failed')
      }
      setTranscription(result as TranscriptionResult)
      setTranscriptionError(null)
    } catch (error) {
      setTranscriptionError({
        jobId: activeJobId,
        message: error instanceof Error ? error.message : 'Transcription failed',
      })
    } finally {
      setIsTranscribing(false)
    }
  }

  const activeTranscription = transcription?.job_id === jobId ? transcription : null
  const activeError = transcriptionError?.jobId === jobId ? transcriptionError : null
  const status = activeTranscription
    ? 'Ready'
    : activeError
      ? 'Transcription failed'
      : jobId
        ? 'Transcribing...'
        : 'Waiting for upload'

  return (
    <section className="panel tabs-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">02 · TRANSCRIPTION</span>
          <h2>Guitar tabs</h2>
        </div>
        <span className="panel-status">{status}</span>
      </div>

      <button
        className="button button-primary analyze-button"
        type="button"
        disabled={!jobId || isTranscribing || endSeconds <= startSeconds}
        onClick={() => void transcribeSelectedRange()}
      >
        {isTranscribing ? 'Analyzing...' : 'Analyze selected range'}
      </button>

      {activeTranscription ? (
        <>
          <div className="song-details">
            <div>
              <strong>Detected notes</strong>
              <span>Tuning · {activeTranscription.tuning.join('  ')}</span>
              <span>Range · {activeTranscription.start_seconds.toFixed(1)}s–{activeTranscription.end_seconds.toFixed(1)}s</span>
              <span>Vision · {activeTranscription.video_observations.filter((item) => item.hands_visible > 0).length} hand-visible frames</span>
              <span>
                Source · {activeTranscription.audio_source === 'demucs_guitar'
                  ? 'Demucs guitar stem'
                  : activeTranscription.audio_source === 'original_fallback'
                    ? 'Original audio (Demucs fallback)'
                    : 'Original audio (legacy result)'}
              </span>
            </div>
            <span className="tempo">{activeTranscription.notes.length} notes</span>
          </div>

          {activeTranscription.notes.length > 0 ? (
            <GuitarTabStaff
              notes={activeTranscription.notes}
              playbackTime={playbackTime}
              durationSeconds={videoDuration}
            />
          ) : (
            <div className="tab-card">
              <div className="measure-label">No notes were detected in this audio.</div>
            </div>
          )}
        </>
      ) : (
        <div className="tab-card">
          <div className="measure-label">
            {activeError?.message ?? (jobId
              ? 'Analyzing audio and mapping notes to strings...'
              : 'Upload a video to generate tabs.')}
          </div>
        </div>
      )}

      <p className="helper-text">
        Each fret number is placed on its detected string at the note’s start time. Scroll horizontally to explore the full recording. This is raw model output, not yet rhythm-quantized.
      </p>
    </section>
  )
}