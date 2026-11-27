import { useState } from 'react'
import VideoPanel from './components/VideoPanel'
import TabsPanel from './components/TabsPanel'
import ChatPanel from './components/ChatPanel'
import type { Calibration } from './components/FretboardCalibration'
import './App.css'

function App() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [videoDuration, setVideoDuration] = useState(0)
  const [playbackTime, setPlaybackTime] = useState(0)
  const [startSeconds, setStartSeconds] = useState(0)
  const [endSeconds, setEndSeconds] = useState(0)
  const [calibration, setCalibration] = useState<Calibration | null>(null)

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="croissantdough home">
          <span className="brand-mark" aria-hidden="true">🥐</span>
          <span>croissantdough</span>
        </a>

        <div className="topbar-center">Guitar transcription workspace</div>

        <button className="button button-subtle" type="button">
          New session
        </button>
      </header>

      <section className="welcome">
        <div>
          <span className="eyebrow">YOUR AI PRACTICE SPACE</span>
          <h1>Generate tabs from any video.</h1>
          <p>Upload a performance, explore the tabs, and ask questions as you learn.</p>
        </div>
        <div className="step-indicator">
          <span className="step-dot" />
          Ready to start
        </div>
      </section>

      <div className="workspace">
        <VideoPanel
          onCalibrationChange={setCalibration}
          onPlaybackTimeChange={setPlaybackTime}
          startSeconds={startSeconds}
          endSeconds={endSeconds}
          onRangeChange={(start, end) => {
            setStartSeconds(start)
            setEndSeconds(end)
            setPlaybackTime(start)
          }}
          setUploadInfo={(nextJobId, duration) => {
            setJobId(nextJobId)
            setVideoDuration(duration)
            setPlaybackTime(0)
            setStartSeconds(0)
            setEndSeconds(duration)
          }}
        />
        <TabsPanel
          calibration={calibration}
          jobId={jobId}
          playbackTime={playbackTime}
          videoDuration={videoDuration}
          startSeconds={startSeconds}
          endSeconds={endSeconds}
        />
        <ChatPanel
          jobId={jobId}
          startSeconds={startSeconds}
          endSeconds={endSeconds}
        />
      </div>

      <footer className="page-footer">
        Your workspace · Transcriptions are examples until processing is connected
      </footer>
    </main>
  )
}

export default App
