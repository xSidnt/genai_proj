import { useState } from 'react'
import VideoPanel from './components/VideoPanel'
import TabsPanel from './components/TabsPanel'
import ChatPanel from './components/ChatPanel'
import './App.css'

function App() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [videoDuration, setVideoDuration] = useState(0)
  const [playbackTime, setPlaybackTime] = useState(0)
  const [startSeconds, setStartSeconds] = useState(0)
  const [endSeconds, setEndSeconds] = useState(0)

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Riffroom home">
          <span className="brand-mark">♪</span>
          <span>riffroom</span>
        </a>

        <div className="topbar-center">Guitar transcription workspace</div>

        <button className="button button-subtle" type="button">
          New session
        </button>
      </header>

      <section className="welcome">
        <div>
          <span className="eyebrow">YOUR AI PRACTICE SPACE</span>
          <h1>Turn a riff into a song.</h1>
          <p>Upload a performance, explore the tabs, and ask questions as you learn.</p>
        </div>
        <div className="step-indicator">
          <span className="step-dot" />
          Ready to start
        </div>
      </section>

      <div className="workspace">
        <VideoPanel
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
          jobId={jobId}
          playbackTime={playbackTime}
          videoDuration={videoDuration}
          startSeconds={startSeconds}
          endSeconds={endSeconds}
        />
        <ChatPanel />
      </div>

      <footer className="page-footer">
        Your workspace · Transcriptions are examples until processing is connected
      </footer>
    </main>
  )
}

export default App