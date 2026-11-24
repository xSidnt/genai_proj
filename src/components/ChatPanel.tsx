import { useState, type FormEvent } from 'react'

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hi! Once your video is transcribed, ask me about the notes, rhythm, or technique.',
    },
  ])
  const [draft, setDraft] = useState('')

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (!message) return

    setMessages((currentMessages) => [
      ...currentMessages,
      { role: 'user', text: message },
    ])
    setDraft('')
  }

  return (
    <section className="panel chat-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">03 · ASSISTANT</span>
          <h2>Ask about your music</h2>
        </div>
        <span className="online-indicator">●</span>
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.map((message, index) => (
          <div
            className={`message message-${message.role}`}
            key={`${message.role}-${index}`}
          >
            {message.text}
          </div>
        ))}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          aria-label="Message"
          placeholder="Ask a question..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button className="send-button" type="submit" aria-label="Send message">
          ↑
        </button>
      </form>

      <p className="helper-text">Chat replies will be connected later.</p>
    </section>
  )
}