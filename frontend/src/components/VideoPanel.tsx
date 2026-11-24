import { useEffect, useState, type ChangeEvent } from 'react'

export default function VideoPanel() {
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!videoFile) {
      setVideoUrl(null)
      return
    }

    const url = URL.createObjectURL(videoFile)
    setVideoUrl(url)

    return () => URL.revokeObjectURL(url)
  }, [videoFile])

  function handleVideoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) setVideoFile(file)
  }

  return (
    <section className="panel video-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">01 · SOURCE</span>
          <h2>Your video</h2>
        </div>
        <span className="panel-status">{videoFile ? 'Ready' : 'No video'}</span>
      </div>

      <div className="video-stage">
        {videoUrl ? (
          <video className="video-preview" src={videoUrl} controls />
        ) : (
          <div className="video-empty">
            <div className="play-icon">▶</div>
            <strong>Your performance goes here</strong>
            <span>Upload a 30–60 second guitar video</span>
          </div>
        )}
      </div>

      <label className="button button-primary upload-button">
        {videoFile ? 'Choose another video' : 'Upload a video'}
        <input
          type="file"
          accept="video/*"
          onChange={handleVideoChange}
          hidden
        />
      </label>

      <p className="helper-text">
        MP4, MOV, or WebM. Video processing will be added later.
      </p>
    </section>
  )
}