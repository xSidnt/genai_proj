import { useEffect, useRef, useState, type ChangeEvent } from 'react'

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
}

export default function VideoPanel({ setUploadInfo, onPlaybackTimeChange }: VideoPanelProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [uploadStatus, setUploadStatus] = useState('No video')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const videoUrlRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current)
    }
  }, [])

  async function handleVideoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

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
      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed')
      }

      setUploadResult(result as UploadResult)
      setUploadStatus('Ready')
      setUploadInfo(
        (result as UploadResult).job_id,
        (result as UploadResult).duration_seconds,
      )
    } catch (error) {
      setUploadStatus('Upload failed')
      setUploadResult(null)
      window.alert(error instanceof Error ? error.message : 'Upload failed')
    }
  }

  return (
    <section className="panel video-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">01 · SOURCE</span>
          <h2>Your video</h2>
        </div>
        <span className="panel-status">{uploadStatus}</span>
      </div>

      <div className="video-stage">
        {videoUrl ? (
          <video
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
          hidden
        />
      </label>

      {uploadResult ? (
        <p className="helper-text">
          {uploadResult.duration_seconds.toFixed(1)}s · {uploadResult.width ?? '?'}×
          {uploadResult.height ?? '?'} · {uploadResult.frame_rate?.toFixed(2) ?? '?'} fps
        </p>
      ) : (
        <p className="helper-text">
          MP4, MOV, or WebM. Maximum length: 60 seconds.
        </p>
      )}
    </section>
  )
}