export default function TabsPanel() {
  return (
    <section className="panel tabs-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">02 · TRANSCRIPTION</span>
          <h2>Guitar tabs</h2>
        </div>
        <span className="panel-status">Example</span>
      </div>

      <div className="song-details">
        <div>
          <strong>Untitled riff</strong>
          <span>Standard tuning · E A D G B E</span>
        </div>
        <span className="tempo">♩ 92 BPM</span>
      </div>

      <div className="tab-card">
        <div className="measure-label">Measure 1</div>
        <pre className="tab-content">{`e|--------0-----------|
B|------1---1---------|
G|----0-------0-------|
D|--2-----------2-----|
A|3-------------------|
E|--------------------|`}</pre>

        <div className="measure-label second-measure">Measure 2</div>
        <pre className="tab-content">{`e|--------0-----3-----|
B|------1---1-----1---|
G|----0---------0-----|
D|--2-----------------|
A|3-------------------|
E|--------------------|`}</pre>
      </div>

      <p className="helper-text">
        Example tabs only — your transcription will appear here.
      </p>
    </section>
  )
}