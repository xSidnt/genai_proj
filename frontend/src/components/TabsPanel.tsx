import { useEffect, useState } from 'react'

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

interface TabsPanelProps {
  jobId: string | null
}

export default function TabsPanel({ jobId }: TabsPanelProps) {
  const [transcription, setTranscription] = useState<TranscriptionResult | null>(null)
  const [status, setStatus] = useState('Waiting for upload')

  useEffect(() => {
    if (!jobId) return

    let cancelled = false
    setTranscription(null)
    setStatus('Transcribing...')

    async function transcribe() {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/transcriptions/${jobId}`,
          { method: 'POST' },
        )
        const result = await response.json()
        if (!response.ok) {
          throw new Error(result.detail || 'Transcription failed')
        }
        if (!cancelled) {
          setTranscription(result as TranscriptionResult)
          setStatus('Ready')
        }
      } catch (error) {
        if (!cancelled) {
          setStatus('Transcription failed')
          window.alert(error instanceof Error ? error.message : 'Transcription failed')
        }
      }
    }

    void transcribe()
    return () => {
      cancelled = true
    }
  }, [jobId])

  const visibleNotes = transcription?.notes
    .filter((note) => note.confidence >= 0.45)
    .slice(0, 40) ?? []

  return (
    <section className="panel tabs-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">02 · TRANSCRIPTION</span>
          <h2>Guitar tabs</h2>
        </div>
        <span className="panel-status">{status}</span>
      </div>

      {transcription ? (
        <>
          <div className="song-details">
            <div>
              <strong>Detected notes</strong>
              <span>Standard tuning · E A D G B E</span>
            </div>
            <span className="tempo">{transcription.notes.length} notes</span>
          </div>

          <div className="tab-card">
            {visibleNotes.length > 0 ? (
              visibleNotes.map((note) => (
                <div className="measure-label" key={`${note.start_seconds}-${note.midi}`}>
                  <strong>{note.pitch}</strong>
                  {' '}· string {note.string} · fret {note.fret}
                  {' '}· {note.start_seconds.toFixed(2)}s
                </div>
              ))
            ) : (
              <div className="measure-label">No confident notes detected yet.</div>
            )}
          </div>
        </>
      ) : (
        <div className="tab-card">
          <div className="measure-label">Upload a video to generate notes.</div>
        </div>
      )}

      <p className="helper-text">
        Basic Pitch output mapped to standard guitar tuning.
      </p>
    </section>
  )
}