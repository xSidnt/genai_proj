interface TabNote {
  pitch: string
  midi: number
  string: number
  fret: number
  start_seconds: number
  duration_seconds: number
  confidence: number
}

interface GuitarTabStaffProps {
  notes: TabNote[]
  playbackTime: number
  durationSeconds: number
  bpm: number
}

const STRINGS = [
  { number: 1, tuning: 'e' },
  { number: 2, tuning: 'B' },
  { number: 3, tuning: 'G' },
  { number: 4, tuning: 'D' },
  { number: 5, tuning: 'A' },
  { number: 6, tuning: 'E' },
]

const LEFT_GUTTER = 34
const LANE_HEIGHT = 30
const PIXELS_PER_SUBDIVISION = 36
const SUBDIVISIONS_PER_MEASURE = 16
const SUBDIVISION_LABELS = ['1', 'e', '&', 'a', '2', 'e', '&', 'a', '3', 'e', '&', 'a', '4', 'e', '&', 'a']

function secondsToSixteenth(seconds: number, bpm: number) {
  const sixteenthDuration = 60 / bpm / 4
  return seconds / sixteenthDuration
}

export default function GuitarTabStaff({
  notes,
  playbackTime,
  durationSeconds,
  bpm,
}: GuitarTabStaffProps) {
  const duration = Math.max(durationSeconds, 1)
  const measureSeconds = 240 / bpm
  const measureCount = Math.max(1, Math.ceil(duration / measureSeconds))
  const playbackSubdivision = secondsToSixteenth(playbackTime, bpm)
  const activeMeasure = Math.min(Math.floor(playbackSubdivision / SUBDIVISIONS_PER_MEASURE), measureCount - 1)

  return (
    <div className="tab-scroll" aria-label="Scrollable BPM-based guitar tablature">
      {Array.from({ length: measureCount }, (_, measureIndex) => {
        const measureStartSubdivision = measureIndex * SUBDIVISIONS_PER_MEASURE
        const measureEndSubdivision = measureStartSubdivision + SUBDIVISIONS_PER_MEASURE
        const rowNotes = notes.filter((note) => {
          const subdivision = secondsToSixteenth(note.start_seconds, bpm)
          return subdivision >= measureStartSubdivision && subdivision < measureEndSubdivision
        })
        const isActive = measureIndex === activeMeasure
        const playheadSubdivision = playbackSubdivision - measureStartSubdivision
        const playheadX = LEFT_GUTTER + playheadSubdivision * PIXELS_PER_SUBDIVISION

        return (
          <section
            className={`tab-segment${isActive ? ' tab-segment-active' : ''}`}
            key={measureIndex}
            aria-label={`Measure ${measureIndex + 1}`}
          >
            <h3 className="tab-segment-heading">
              Measure {measureIndex + 1} · 4/4 · {bpm} BPM
            </h3>
            <div className="tab-staff">
              <div className="tab-ruler">
                {SUBDIVISION_LABELS.map((label, subdivisionIndex) => (
                  <span
                    className="tab-time-tick"
                    key={subdivisionIndex}
                    style={{ left: `${LEFT_GUTTER + subdivisionIndex * PIXELS_PER_SUBDIVISION}px` }}
                  >
                    {label}
                  </span>
                ))}
              </div>

              <div className="tab-strings">
                {isActive && playheadSubdivision >= 0 && playheadSubdivision <= SUBDIVISIONS_PER_MEASURE && (
                  <span
                    className="tab-playhead"
                    style={{ left: `${playheadX}px` }}
                    aria-label={`BPM position measure ${measureIndex + 1}`}
                  />
                )}

                {STRINGS.map((string, stringRow) => (
                  <div
                    className="tab-string-row"
                    key={string.number}
                    style={{ top: `${stringRow * LANE_HEIGHT}px`, height: `${LANE_HEIGHT}px` }}
                  >
                    <span className="tab-tuning-label">{string.tuning}</span>
                    <span className="tab-string-line" />
                  </div>
                ))}

                {Array.from({ length: SUBDIVISIONS_PER_MEASURE + 1 }, (_, subdivisionIndex) => (
                  <span
                    className={subdivisionIndex % 4 === 0 ? 'tab-beat-line tab-beat-line-major' : 'tab-beat-line'}
                    key={subdivisionIndex}
                    style={{ left: `${LEFT_GUTTER + subdivisionIndex * PIXELS_PER_SUBDIVISION}px` }}
                  />
                ))}

                {rowNotes.map((note, index) => {
                  const stringRow = STRINGS.findIndex((string) => string.number === note.string)
                  if (stringRow < 0) return null

                  const exactSubdivision = secondsToSixteenth(note.start_seconds, bpm)
                  const snappedSubdivision = Math.round(exactSubdivision)
                  const positionInMeasure = snappedSubdivision - measureStartSubdivision

                  return (
                    <span
                      className="tab-note"
                      key={`${note.midi}-${note.string}-${note.start_seconds}-${index}`}
                      style={{
                        left: `${LEFT_GUTTER + positionInMeasure * PIXELS_PER_SUBDIVISION}px`,
                        top: `${stringRow * LANE_HEIGHT + LANE_HEIGHT / 2}px`,
                        opacity: Math.max(0.48, Math.min(1, note.confidence)),
                      }}
                      title={`${note.pitch}, string ${note.string}, fret ${note.fret}, measure ${measureIndex + 1}, sixteenth ${positionInMeasure + 1}, confidence ${(note.confidence * 100).toFixed(0)}%`}
                    >
                      {note.fret}
                    </span>
                  )
                })}
              </div>
            </div>
          </section>
        )
      })}
    </div>
  )
}
