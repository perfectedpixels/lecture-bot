import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, MessageSquare, SendHorizonal, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { postChat } from '../api/client'

// Simplified vs. the ux-team-kb reference: lecture-bot's /api/chat returns a
// single JSON response, not an SSE stream, so there's no token-by-token
// reveal here — just a loading state then the full answer.
export function CardChatModal({ card, onClose, onAskInChat }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const startedRef = useRef(false)
  const endRef = useRef(null)

  const ask = async (text) => {
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setBusy(true)
    try {
      const data = await postChat({ message: text })
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer, sources: data.sources }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong answering that.', error: true },
      ])
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    void ask(card.title)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  const send = () => {
    const t = input.trim()
    if (!t || busy) return
    setInput('')
    void ask(t)
  }

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="flex h-[80vh] w-full max-w-2xl flex-col rounded-2xl border border-white/15 bg-gradient-to-br from-[#3a1a63] to-[#1a0f2e] shadow-2xl"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <h2 className="text-sm font-semibold text-white">{card.title}</h2>
            <div className="flex items-center gap-1">
              {onAskInChat && (
                <button
                  type="button"
                  onClick={() => onAskInChat(card.title)}
                  title="Continue this conversation in the main Chat"
                  className="flex items-center gap-1 rounded-md border border-[#9D4EDD]/60 bg-[#9D4EDD]/15 px-2 py-1 text-xs font-medium text-[#E0B0FF] hover:bg-[#9D4EDD]/25"
                >
                  <MessageSquare size={13} />
                  Continue in Chat
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1 text-white/60 hover:bg-white/10 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2 text-sm ${
                    m.role === 'user'
                      ? 'bg-gradient-to-br from-[#8938f6] to-[#b565ff] text-white'
                      : m.error
                      ? 'bg-red-900 text-white'
                      : 'bg-black/30 text-white/90'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.sources && m.sources.length > 0 && (
                    <details className="mt-2 text-xs text-white/50">
                      <summary className="cursor-pointer hover:text-white/80">
                        Sources ({m.sources.length})
                      </summary>
                      <ul className="mt-1 space-y-1 pl-3">
                        {m.sources.map((s, j) => (
                          <li key={j} className="text-[11px]">{s}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl bg-black/30 px-4 py-2 text-sm text-white/80">
                  <Loader2 size={14} className="animate-spin" />
                  Thinking…
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="flex items-center gap-2 border-t border-white/10 p-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Ask a follow-up…"
              className="flex-1 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-[#9D4EDD]"
              disabled={busy}
            />
            <button
              type="button"
              onClick={send}
              disabled={busy || !input.trim()}
              className="rounded-lg bg-white/15 border-2 border-white/30 p-2 text-white hover:bg-white/25 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <SendHorizonal size={16} />
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
