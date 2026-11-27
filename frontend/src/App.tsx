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
        <a className="brand" href="/" aria-label="CroissantDough home">
          <img className="brand-mark" src="/croissantdough.png" alt="" width="46" height="25" />
          <span>CroissantDough</span>
        </a>

        <span className="topbar-label">Guitar transcription workspace</span>
      </header>

      <section className="welcome">
        <h1>Turn guitar videos into tabs.</h1>
        <p>Upload a guitar video, follow the tab during playback, and ask about what you hear.</p>
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
    </main>
  )
}

export default App
