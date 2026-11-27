import { useState } from 'react'
import GuitarTabStaff from './GuitarTabStaff'
import type { Calibration } from './FretboardCalibration'

type Transcriber = 'basic_pitch' | 'tabcnn'
type AudioInput = 'guitar_stem' | 'original'
type NoteMode = 'polyphonic' | 'lead'
type VisionMode = 'audio_only' | 'tracked' | 'fixed' | 'configured'

interface AnalysisSettings {
  transcriber: Transcriber
  audioInput: AudioInput
  noteMode: NoteMode
  visionMode: VisionMode
}

const presets = [
  {
    label: 'Solo electric guitar',
    settings: { transcriber: 'tabcnn', audioInput: 'original', noteMode: 'polyphonic', visionMode: 'audio_only' },
  },
  {
    label: 'Pitch and timing',
    settings: { transcriber: 'basic_pitch', audioInput: 'original', noteMode: 'polyphonic', visionMode: 'audio_only' },
  },
  {
    label: 'Single-note lead with backing',
    settings: { transcriber: 'tabcnn', audioInput: 'guitar_stem', noteMode: 'lead', visionMode: 'fixed' },
  },
] satisfies { label: string, settings: AnalysisSettings }[]

interface TabNote {
  pitch: string
  midi: number
  string: number
  fret: number
  start_seconds: number
  grid_seconds?: number | null
  duration_seconds: number
  confidence: number
  technique?: 'bend' | 'slide' | null
  technique_target_fret?: number | null
  bend_semitones?: number | null
  visual_status?: string
  visual_confidence?: number
  combined_confidence?: number
  visual_string?: number
  visual_fret?: number
  visual_index_fret?: number | null
  visual_hand_fret?: number | null
  audio_string?: number | null
  audio_fret?: number | null
}

interface VideoObservation {
  timestamp_seconds: number
  hands_visible: number
  fretting_hand_visible: boolean
  neck_visible: boolean
  visual_confidence: number
  measure_anchor?: boolean
  fretboard_reanchored?: boolean
}

interface TranscriptionResult {
  job_id: string
  status: string
  tuning: string[]
  tempo_bpm: number | null
  tempo_source?: string | null
  analysis_profile?: string | null
  notes: TabNote[]
  audio_source: string
  start_seconds: number
  end_seconds: number
  video_observations: VideoObservation[]
  vision_seconds?: number | null
  visionMode?: VisionMode
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
  calibration: Calibration | null
}

export default function TabsPanel({
  jobId,
  playbackTime,
  videoDuration,
  startSeconds,
  endSeconds,
  calibration,
}: TabsPanelProps) {
  const [transcription, setTranscription] = useState<TranscriptionResult | null>(null)
  const [transcriptionError, setTranscriptionError] = useState<TranscriptionErrorState | null>(null)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [tempoOverride, setTempoOverride] = useState<{ jobId: string | null, value: string } | null>(null)
  const [showAudioPositions, setShowAudioPositions] = useState(false)
  const [settings, setSettings] = useState<AnalysisSettings>(presets[0].settings)
  const { transcriber, audioInput, noteMode, visionMode } = settings
  const preset = presets.find(({ settings: presetSettings }) => (
    presetSettings.transcriber === transcriber
    && presetSettings.audioInput === audioInput
    && presetSettings.noteMode === noteMode
    && presetSettings.visionMode === visionMode
  ))
  const needsCalibration = visionMode === 'tracked' || visionMode === 'fixed'

  const transcribeSelectedRange = async () => {
    if (!jobId || endSeconds <= startSeconds || (needsCalibration && !calibration)) return
    const fretboard = needsCalibration ? calibration : null
    const activeJobId = jobId
    setIsTranscribing(true)
    setTranscriptionError(null)

    try {
      const params = new URLSearchParams({
        start_seconds: startSeconds.toFixed(3),
        end_seconds: endSeconds.toFixed(3),
        transcriber,
        audio_input: audioInput,
        note_mode: noteMode,
        vision_mode: visionMode === 'configured' ? 'configured' : 'audio_only',
      })
      if ((noteMode === 'lead' || fretboard) && manualTempo !== null) params.set('grid_bpm', String(bpm))
      const response = await fetch(
        `http://127.0.0.1:8000/api/transcriptions/${activeJobId}?${params}`,
        fretboard
          ? {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(visionMode === 'fixed' ? { ...fretboard, reference_seconds: undefined } : fretboard),
            }
          : { method: 'POST' },
      )
      const result = await response.json()
      if (!response.ok) {
        const detail = Array.isArray(result.detail) ? result.detail[0]?.msg : result.detail
        throw new Error(detail || 'Transcription failed')
      }
      const transcriptionResult = result as TranscriptionResult
      setTranscription({ ...transcriptionResult, visionMode })
      setShowAudioPositions(false)
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
  const usedCalibration = activeTranscription?.visionMode === 'tracked' || activeTranscription?.visionMode === 'fixed'
  const usedTabcnn = activeTranscription?.analysis_profile?.startsWith('tabcnn:')
  const activeError = transcriptionError?.jobId === jobId ? transcriptionError : null
  const manualTempo = tempoOverride?.jobId === jobId ? tempoOverride.value : null
  const detectedTempo = activeTranscription?.tempo_bpm ?? null
  const fallbackBpm = detectedTempo ?? 120
  const bpm = Math.round(Math.max(30, Math.min(300, Number(manualTempo) || fallbackBpm)))
  const [, , , analysisMode, analysisGrid] = activeTranscription?.analysis_profile?.split(':') ?? []
  const leadGridBpm = analysisMode === 'lead' ? Number(analysisGrid) || fallbackBpm : null
  const supportedNotes = activeTranscription?.notes.filter((note) => note.visual_status === 'calibrated-visible') ?? []
  const handPositionCount = activeTranscription?.notes.filter((note) => note.visual_index_fret != null).length ?? 0
  const fingertipPositionCount = activeTranscription?.notes.filter((note) => note.visual_hand_fret != null).length ?? 0
  const handConflictCount = activeTranscription?.notes.filter((note) => note.visual_status === 'calibrated-conflict').length ?? 0
  const changedCount = activeTranscription?.notes.filter((note) => note.audio_string != null && (
    note.string !== note.audio_string || note.fret !== note.audio_fret
  )).length ?? 0
  const observations = activeTranscription?.video_observations ?? []
  const handFrames = observations.filter((frame) => frame.hands_visible > 0).length
  const fingertipFrames = observations.filter((frame) => frame.fretting_hand_visible).length
  const trackedFrames = observations.filter((frame) => frame.neck_visible).length
  const measureAnchors = observations.filter((frame) => frame.measure_anchor)
  const reanchoredMeasures = measureAnchors.filter((frame) => frame.fretboard_reanchored).length
  const displayedNotes = activeTranscription?.notes.map((note) => showAudioPositions
    ? { ...note, string: note.audio_string ?? note.string, fret: note.audio_fret ?? note.fret,
        technique: note.technique === 'slide' ? null : note.technique, visual_status: undefined,
        visual_index_fret: undefined, visual_hand_fret: undefined }
    : note) ?? []
  const status = isTranscribing
    ? 'Analyzing…'
    : activeError
      ? 'Transcription failed'
      : activeTranscription
        ? 'Ready'
        : jobId
          ? 'Ready to analyze'
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

      <div className="transcription-options">
        <label>
          Preset
          <select value={preset?.label ?? ''} disabled={isTranscribing} onChange={(event) => {
            const selected = presets.find(({ label }) => label === event.target.value)
            if (selected) setSettings(selected.settings)
          }}>
            <option value="" disabled>Custom</option>
            {presets.map(({ label }) => <option key={label}>{label}</option>)}
          </select>
        </label>
        <label>
          Note model
          <select value={transcriber} disabled={isTranscribing} onChange={(event) => {
            const nextModel = event.target.value as Transcriber
            setSettings({
              ...settings,
              transcriber: nextModel,
              visionMode: nextModel === 'tabcnn' && visionMode === 'configured' ? 'audio_only' : visionMode,
            })
          }}>
            <option value="basic_pitch">Basic Pitch + playable fingering</option>
            <option value="tabcnn">Electric Guitar (TabCNN)</option>
          </select>
        </label>
        <label>
          Audio input
          <select value={audioInput} disabled={isTranscribing} onChange={(event) => setSettings({ ...settings, audioInput: event.target.value as AudioInput })}>
            <option value="guitar_stem">Isolated guitar</option>
            <option value="original">Original audio</option>
          </select>
        </label>
        <label>
          Arrangement
          <select value={noteMode} disabled={isTranscribing} onChange={(event) => setSettings({ ...settings, noteMode: event.target.value as NoteMode })}>
            <option value="polyphonic">Melody and chords</option>
            <option value="lead">Single-note lead</option>
          </select>
        </label>
        <label>
          Vision
          <select value={visionMode} disabled={isTranscribing} onChange={(event) => setSettings({ ...settings, visionMode: event.target.value as VisionMode })}>
            <option value="audio_only">Off</option>
            <option value="tracked">Track fretboard</option>
            <option value="fixed">Fixed calibration</option>
            {transcriber === 'basic_pitch' && <option value="configured">Server-configured vision</option>}
          </select>
        </label>
      </div>

      {needsCalibration && !calibration && (
        <p className="helper-text">Mark the fretboard in Your video to use this vision setting.</p>
      )}
      {leadGridBpm !== null && bpm !== leadGridBpm && (
        <p className="helper-text">This lead tab uses {leadGridBpm} BPM. Analyze again to apply {bpm} BPM to its note selection.</p>
      )}

      <button
        className="button button-primary analyze-button"
        type="button"
        disabled={!jobId || isTranscribing || endSeconds <= startSeconds || (needsCalibration && !calibration)}
        onClick={() => void transcribeSelectedRange()}
      >
        {isTranscribing ? 'Analyzing...' : needsCalibration ? 'Analyze with audio + vision' : 'Analyze selected range'}
      </button>

      {activeError && <p className="helper-text" role="alert">{activeError.message}</p>}

      <div className="bpm-controls">
        <label>
          BPM
          <input
            type="number"
            min={30}
            max={300}
            step={1}
            value={manualTempo ?? fallbackBpm}
            onChange={(event) => setTempoOverride({ jobId, value: event.target.value })}
            onBlur={() => {
              if (manualTempo !== null) setTempoOverride({ jobId, value: String(bpm) })
            }}
          />
        </label>
        <span>
          {detectedTempo ? `Estimated ${detectedTempo} BPM${activeTranscription?.tempo_source === 'original' ? ' from original audio' : ''} · ` : 'No tempo detected · '}
          4/4 · 16 subdivisions
        </span>
        {manualTempo !== null && (
          <button className="button button-subtle" type="button" onClick={() => setTempoOverride(null)}>
            Use estimated BPM
          </button>
        )}
      </div>

      {activeTranscription ? (
        <>
          <div className="song-details">
            <div>
              <strong>Detected notes</strong>
              <span>Tuning · {activeTranscription.tuning.join('  ')}</span>
              <span>Range · {activeTranscription.start_seconds.toFixed(1)}s–{activeTranscription.end_seconds.toFixed(1)}s</span>
              <span>Model · {usedTabcnn ? 'Electric Guitar (TabCNN)' : 'Basic Pitch + playable fingering'}</span>
              {leadGridBpm !== null && <span>Single-note lead · one note at most per sixteenth at {leadGridBpm} BPM</span>}
              {usedCalibration ? (
                <>
                  <span>
                    Audio + vision · {supportedNotes.length} visually supported · {changedCount} positions changed
                    {activeTranscription.vision_seconds != null && ` · ${activeTranscription.vision_seconds.toFixed(2)}s vision time`}
                  </span>
                  <span>Hand position · {handPositionCount} notes from index · {fingertipPositionCount} from other fingertips · {handConflictCount} conflicts</span>
                  <span>Sampled frames · {handFrames}/{observations.length} with hands · {fingertipFrames}/{observations.length} with fingertips in the marked area</span>
                  {activeTranscription.visionMode === 'tracked' ? (
                    <span>Fretboard tracked · {trackedFrames}/{observations.length} sampled frames · {reanchoredMeasures}/{measureAnchors.length} measure anchors matched</span>
                  ) : <span>Fretboard · Fixed calibration</span>}
                </>
              ) : <span>Vision · {activeTranscription.visionMode === 'configured' ? `${handFrames} hand-visible frames` : 'Off'}</span>}
              <span>
                Source · {activeTranscription.audio_source === 'demucs_guitar'
                  ? 'Demucs guitar stem'
                  : activeTranscription.audio_source === 'original_fallback'
                    ? 'Original audio (Demucs fallback)'
                    : 'Original audio'}
              </span>
            </div>
            <span className="tempo">{activeTranscription.notes.length} notes</span>
          </div>

          {usedCalibration && (
            <div className="vision-comparison">
              <label>
                <input type="checkbox" checked={showAudioPositions} onChange={(event) => setShowAudioPositions(event.target.checked)} />
                Show audio-only positions
              </label>
              <p className="helper-text">Local comparison results are temporary. Chat uses the last saved analysis.</p>
              {!showAudioPositions && handConflictCount > 0 && (
                <p className="helper-text">Orange notes mark fingerings that conflict with the estimated hand position. Hover to see the estimate.</p>
              )}
            </div>
          )}

          {activeTranscription.notes.length > 0 ? (
            <GuitarTabStaff
              notes={displayedNotes}
              playbackTime={playbackTime}
              durationSeconds={videoDuration}
              bpm={leadGridBpm ?? bpm}
            />
          ) : (
            <div className="tab-card">
              <div className="measure-label">No notes were detected in this audio.</div>
            </div>
          )}
          {displayedNotes.some((note) => note.technique) && (
            <p className="helper-text">b and / mark possible bends and slides. Hover over a note for details.</p>
          )}
        </>
      ) : (
        <div className="tab-card">
          <div className="measure-label">
            {jobId ? 'Analyze the selected range to generate tabs.' : 'Upload a video to generate tabs.'}
          </div>
        </div>
      )}

      <p className="helper-text">
        {leadGridBpm !== null
          ? 'The lead tab follows playback. Hover over a note to see its detected onset.'
          : 'The tab follows video playback and shows detected note times against an estimated beat grid.'}
      </p>
    </section>
  )
}
