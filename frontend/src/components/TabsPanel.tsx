import { useEffect, useState } from 'react'
import GuitarTabStaff from './GuitarTabStaff'

interface TabNote {
  pitch: string
  midi: number
  string: number
  fret: number
  start_seconds: number
  duration_seconds: number
  confidence: number
}

interface TranscriptionResult {
  job_id: string
  status: string
  tuning: string[]
  tempo_bpm: number | null
  notes: TabNote[]
}

interface TranscriptionErrorState {
  jobId: string
  message: string
}

interface TabsPanelProps {
  jobId: string | null
  playbackTime: number
  videoDuration: number
}

export default function TabsPanel({ jobId, playbackTime, videoDuration }: TabsPanelProps) {
  const [transcription, setTranscription] = useState<TranscriptionResult | null>(null)
  const [transcriptionError, setTranscriptionError] = useState<TranscriptionErrorState | null>(null)

  useEffect(() => {
    if (!jobId) return
    const activeJobId = jobId

    let cancelled = false

    async function transcribe() {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/transcriptions/${activeJobId}`,
          { method: 'POST' },
        )
        const result = await response.json()
        if (!response.ok) {
          throw new Error(result.detail || 'Transcription failed')
        }
        if (!cancelled) {
          setTranscription(result as TranscriptionResult)
          setTranscriptionError(null)
        }
      } catch (error) {
        if (!cancelled) {
          setTranscriptionError({
            jobId: activeJobId,
            message: error instanceof Error ? error.message : 'Transcription failed',
          })
        }
      }
    }

    void transcribe()
    return () => {
      cancelled = true
    }
  }, [jobId])

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

      {activeTranscription ? (
        <>
          <div className="song-details">
            <div>
              <strong>Detected notes</strong>
              <span>Tuning · {activeTranscription.tuning.join('  ')}</span>
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