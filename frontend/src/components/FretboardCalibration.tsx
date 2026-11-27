import { useState, type MouseEvent, type RefObject } from 'react'

interface ImagePoint {
  x: number
  y: number
}

export interface Calibration {
  start_fret: number
  reference_fret: number
  reference_seconds: number
  points: ImagePoint[]
}

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>
  onChange: (calibration: Calibration | null) => void
}

export default function FretboardCalibration({ videoRef, onChange }: Props) {
  const [snapshot, setSnapshot] = useState<{ url: string, time: number } | null>(null)
  const [points, setPoints] = useState<ImagePoint[]>([])
  const [startFret, setStartFret] = useState(0)
  const [fret, setFret] = useState(12)

  const firstEndOption = Math.max(2, startFret + 1)
  const startWire = startFret === 0 ? 'the nut' : `the fret ${startFret} wire`
  const targets = [
    `Low E at ${startWire}`,
    `High E at ${startWire}`,
    `High E at the fret ${fret} wire`,
    `Low E at the fret ${fret} wire`,
  ]

  function captureFrame() {
    const video = videoRef.current
    if (!video || video.readyState < 2) return

    video.pause()
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return

    context.drawImage(video, 0, 0)
    setSnapshot({ url: canvas.toDataURL('image/jpeg'), time: video.currentTime })
    setPoints([])
    onChange(null)
  }

  function markPoint(event: MouseEvent<HTMLButtonElement>) {
    if (!snapshot || points.length === targets.length || event.detail === 0) return

    const bounds = event.currentTarget.getBoundingClientRect()
    const nextPoints = [...points, {
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    }]
    setPoints(nextPoints)
    if (nextPoints.length === targets.length) {
      onChange({ start_fret: startFret, reference_fret: fret, reference_seconds: snapshot.time, points: nextPoints })
    }
  }

  return (
    <div className="fretboard-calibration">
      <button className="button button-subtle" type="button" onClick={captureFrame}>
        {snapshot ? 'Capture another frame' : 'Calibrate fretboard'}
      </button>
      {!snapshot && <p className="helper-text">Pause on a clear frame with visible fret wires or inlays. The app will try to follow the marked area as the guitar moves.</p>}
      {snapshot && (
        <>
          <p className="helper-text">Choose two visible fret wires that bracket the fretting hand. Use the same frame for all four points.</p>
          <label>
            Start wire
            <select value={startFret} onChange={(event) => {
              const nextStart = Number(event.target.value)
              setStartFret(nextStart)
              setFret(Math.max(fret, nextStart + 1))
              setPoints([])
              onChange(null)
            }}>
              {Array.from({ length: 24 }, (_, number) => (
                <option key={number} value={number}>{number === 0 ? 'Nut' : number}</option>
              ))}
            </select>
          </label>
          <label>
            End wire
            <select value={fret} onChange={(event) => {
              setFret(Number(event.target.value))
              setPoints([])
              onChange(null)
            }}>
              {Array.from({ length: 25 - firstEndOption }, (_, index) => index + firstEndOption).map((number) => (
                <option key={number} value={number}>{number}</option>
              ))}
            </select>
          </label>
          <p className="helper-text" aria-live="polite">
            {points.length === targets.length
              ? 'Fretboard marked. Choose Track fretboard or Fixed calibration in the Vision settings.'
              : `Point ${points.length + 1} of 4 · ${targets[points.length]}`}
          </p>
          <button className="fretboard-frame" type="button" onClick={markPoint} aria-label={targets[points.length] ?? 'Calibrated fretboard'}>
            <img src={snapshot.url} alt="Captured video frame for fretboard calibration" />
            {points.length === targets.length && (
              <span
                aria-hidden="true"
                className="fretboard-area"
                style={{ clipPath: `polygon(${points.map((point) => `${point.x * 100}% ${point.y * 100}%`).join(', ')})` }}
              />
            )}
            {points.map((point, index) => (
              <span className="fretboard-point" key={index} style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}>
                {index + 1}
              </span>
            ))}
          </button>
          {points.length > 0 && (
            <button className="button button-subtle" type="button" onClick={() => {
              setPoints(points.slice(0, -1))
              onChange(null)
            }}>
              Undo last point
            </button>
          )}
        </>
      )}
    </div>
  )
}
