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
}

const STRINGS = [
  { number: 1, tuning: 'e' },
  { number: 2, tuning: 'B' },
  { number: 3, tuning: 'G' },
  { number: 4, tuning: 'D' },
  { number: 5, tuning: 'A' },
  { number: 6, tuning: 'E' },
]

const PIXELS_PER_SECOND = 72
const LEFT_GUTTER = 34
const LANE_HEIGHT = 30
const WINDOW_SECONDS = 8

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export default function GuitarTabStaff({
  notes,
  playbackTime,
  durationSeconds,
}: GuitarTabStaffProps) {
  const duration = Math.max(
    durationSeconds,
    1,
    ...notes.map((note) => note.start_seconds + note.duration_seconds),
  )
  const rowCount = Math.max(1, Math.ceil(duration / WINDOW_SECONDS))
  const ticks = Array.from({ length: WINDOW_SECONDS + 1 }, (_, second) => second)
  const activeRow = Math.min(Math.floor(playbackTime / WINDOW_SECONDS), rowCount - 1)

  return (
    <div className="tab-scroll" aria-label="Scrollable guitar tablature">
      {Array.from({ length: rowCount }, (_, rowIndex) => {
        const startSeconds = rowIndex * WINDOW_SECONDS
        const endSeconds = Math.min(startSeconds + WINDOW_SECONDS, duration)
        const rowNotes = notes.filter(
          (note) => note.start_seconds >= startSeconds && note.start_seconds < startSeconds + WINDOW_SECONDS,
        )
        const isActive = rowIndex === activeRow
        const playheadX = LEFT_GUTTER + (playbackTime - startSeconds) * PIXELS_PER_SECOND

        return (
          <section
            className={`tab-segment${isActive ? ' tab-segment-active' : ''}`}
            key={rowIndex}
            aria-label={`Tab timeline ${formatTime(startSeconds)} to ${formatTime(endSeconds)}`}
          >
            <h3 className="tab-segment-heading">
              {formatTime(startSeconds)} – {formatTime(endSeconds)}
            </h3>
            <div className="tab-staff">
              <div className="tab-ruler">
                {ticks.map((second) => (
                  <span
                    className="tab-time-tick"
                    key={second}
                    style={{ left: `${LEFT_GUTTER + second * PIXELS_PER_SECOND}px` }}
                  >
                    {formatTime(startSeconds + second)}
                  </span>
                ))}
              </div>

              <div className="tab-strings">
                {isActive && (
                  <span
                    className="tab-playhead"
                    style={{ left: `${playheadX}px` }}
                    aria-label={`Video position ${formatTime(playbackTime)}`}
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

                {ticks.map((second) => (
                  <span
                    className="tab-beat-line"
                    key={second}
                    style={{ left: `${LEFT_GUTTER + second * PIXELS_PER_SECOND}px` }}
                  />
                ))}

                {rowNotes.map((note, index) => {
                  const stringRow = STRINGS.findIndex((string) => string.number === note.string)
                  if (stringRow < 0) return null

                  return (
                    <span
                      className="tab-note"
                      key={`${note.midi}-${note.string}-${note.start_seconds}-${index}`}
                      style={{
                        left: `${LEFT_GUTTER + (note.start_seconds - startSeconds) * PIXELS_PER_SECOND}px`,
                        top: `${stringRow * LANE_HEIGHT + LANE_HEIGHT / 2}px`,
                        opacity: Math.max(0.48, Math.min(1, note.confidence)),
                      }}
                      title={`${note.pitch}, string ${note.string}, fret ${note.fret}, ${note.start_seconds.toFixed(2)} seconds, confidence ${(note.confidence * 100).toFixed(0)}%`}
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
