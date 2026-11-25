import { useState, type FormEvent } from 'react'

interface ChatPanelProps {
  jobId: string | null
  startSeconds: number
  endSeconds: number
}

export default function ChatPanel({
  jobId,
  startSeconds,
  endSeconds,
}: ChatPanelProps) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hi! Once your video is transcribed, ask me about the notes, rhythm, or technique.',
    },
  ])
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (!message || !jobId || isSending) return

    setMessages((currentMessages) => [
      ...currentMessages,
      { role: 'user', text: message },
    ])
    setDraft('')
    setIsSending(true)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
          message,
          start_seconds: startSeconds,
          end_seconds: endSeconds,
        }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Chat request failed')
      setMessages((currentMessages) => [
        ...currentMessages,
        { role: 'assistant', text: result.reply as string },
      ])
    } catch (error) {
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: 'assistant',
          text: error instanceof Error ? error.message : 'Chat request failed',
        },
      ])
    } finally {
      setIsSending(false)
    }
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
        <button
          className="send-button"
          type="submit"
          aria-label="Send message"
          disabled={isSending || !jobId}
        >
          {isSending ? '…' : '↑'}
        </button>
      </form>

      <p className="helper-text">
        Answers use the detected tabs and selected analysis range.
      </p>
    </section>
  )
}