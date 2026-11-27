import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import FretboardCalibration, { type Calibration } from './FretboardCalibration'

interface UploadResult {
  job_id: string
  status: string
  duration_seconds: number
  width: number | null
  height: number | null
  frame_rate: number | null
  audio_path: string
}

interface VideoPanelProps {
  setUploadInfo: (jobId: string, durationSeconds: number) => void
  onPlaybackTimeChange: (seconds: number) => void
  startSeconds: number
  endSeconds: number
  onRangeChange: (startSeconds: number, endSeconds: number) => void
  onCalibrationChange: (calibration: Calibration | null) => void
}

export default function VideoPanel({
  setUploadInfo,
  onPlaybackTimeChange,
  startSeconds,
  endSeconds,
  onRangeChange,
  onCalibrationChange,
}: VideoPanelProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState('No video')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const videoUrlRef = useRef<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    return () => {
      if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current)
    }
  }, [])

  async function handleVideoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

    onCalibrationChange(null)
    if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current)
    const nextVideoUrl = URL.createObjectURL(file)
    videoUrlRef.current = nextVideoUrl
    setVideoUrl(nextVideoUrl)
    setVideoFile(file)
    setUploadResult(null)
    setUploadStatus('Uploading...')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/uploads', {
        method: 'POST',
        body: formData,
      })

      const result = await response.json()
      if (nextVideoUrl !== videoUrlRef.current) return
      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed')
      }

      setUploadResult(result as UploadResult)
      setUploadStatus('Ready')
      setUploadInfo(
        (result as UploadResult).job_id,
        (result as UploadResult).duration_seconds,
      )
      onRangeChange(0, (result as UploadResult).duration_seconds)
    } catch (error) {
      if (nextVideoUrl !== videoUrlRef.current) return
      setUploadStatus('Upload failed')
      setUploadResult(null)
      window.alert(error instanceof Error ? error.message : 'Upload failed')
    }
  }

  return (
    <section className="panel video-panel">
      <div className="panel-heading">
        <h2>Your video</h2>
        <span className="panel-status">{uploadStatus}</span>
      </div>

      <div className="video-stage">
        {videoUrl ? (
          <video
            ref={videoRef}
            className="video-preview"
            src={videoUrl}
            controls
            onTimeUpdate={(event) => onPlaybackTimeChange(event.currentTarget.currentTime)}
            onSeeked={(event) => onPlaybackTimeChange(event.currentTarget.currentTime)}
          />
        ) : (
          <div className="video-empty">
            <div className="play-icon">▶</div>
            <strong>Your performance goes here</strong>
            <span>Upload a video under 60 seconds</span>
          </div>
        )}
      </div>

      <label className="button button-primary upload-button">
        {videoFile ? 'Choose another video' : 'Upload a video'}
        <input
          type="file"
          accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
          onChange={handleVideoChange}
          className="upload-input"
        />
      </label>

      {uploadResult ? (
        <>
          <div className="analysis-range">
            <div className="analysis-range-heading">
              <strong>Analysis range</strong>
              <span>{(endSeconds - startSeconds).toFixed(1)}s selected</span>
            </div>
            <div className="analysis-range-fields">
              <label>
                Start
                <input
                  type="number"
                  min={0}
                  max={Math.max(0, endSeconds - 0.5)}
                  step={0.1}
                  value={startSeconds}
                  onChange={(event) => {
                    const nextStart = Math.max(0, Math.min(Number(event.target.value), endSeconds - 0.5))
                    onRangeChange(nextStart, endSeconds)
                  }}
                />
              </label>
              <label>
                End
                <input
                  type="number"
                  min={Math.min(uploadResult.duration_seconds, startSeconds + 0.5)}
                  max={uploadResult.duration_seconds}
                  step={0.1}
                  value={endSeconds}
                  onChange={(event) => {
                    const nextEnd = Math.min(uploadResult.duration_seconds, Math.max(startSeconds + 0.5, Number(event.target.value)))
                    onRangeChange(startSeconds, nextEnd)
                  }}
                />
              </label>
            </div>
          </div>

          <p className="helper-text">
            {uploadResult.duration_seconds.toFixed(1)}s · {uploadResult.width ?? '?'}×
            {uploadResult.height ?? '?'} · {uploadResult.frame_rate?.toFixed(2) ?? '?'} fps
          </p>
          <FretboardCalibration videoRef={videoRef} onChange={onCalibrationChange} />
        </>
      ) : (
        <p className="helper-text">
          MP4, MOV, or WebM. Maximum length: 60 seconds.
        </p>
      )}
    </section>
  )
}
