import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { ChatBubbleLeftRightIcon, SpeakerWaveIcon, SpeakerXMarkIcon } from '@heroicons/react/24/outline'
import { NotebookPen, Sparkles, X } from 'lucide-react'
import { ExploreCanvas } from './explore/ExploreCanvas'
import { getUpcomingAssignments, sendChatMessage } from './api/client'

function App() {
  const [view, setView] = useState('chat')
  const [messages, setMessages] = useState([])
  // Before the first message, the input sits centered so it's impossible to
  // miss; once the conversation starts, it animates down to its permanent
  // dock at the bottom (framer-motion's `layout` prop handles the slide).
  const hasMessages = messages.length > 0
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // Defaults off; when on, audio auto-plays for each new response (no
  // separate autoplay toggle -- one button, one concept).
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  // Reply language toggle, ported from the original Streamlit app's
  // "Language / 语言" English/中文 buttons (app/streamlit_app.py) -- the
  // student may type in either language regardless of this setting.
  const [responseLanguage, setResponseLanguage] = useState('en')
  const audioRef = useRef(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  // Cross-view bridging: Chat -> Explore seeds the canvas with a topic and
  // switches view; Explore -> Chat seeds the chat input with a question,
  // switches view, and auto-sends it. Mirrors ux-team-kb's AskPanel<->Explore
  // seed/nonce pattern (a nonce, not just the value, so re-selecting the same
  // topic/question twice in a row still re-triggers).
  const [exploreSeed, setExploreSeed] = useState(null)
  const [chatSeed, setChatSeed] = useState(null)

  // Canvas homework-help: once a student clicks "Get homework help" on an
  // assignment, every subsequent question stays grounded in that assignment's
  // rubric until they explicitly exit — mirrors the original Streamlit app's
  // sticky homework_help_mode (it never auto-resets either).
  const [assignments, setAssignments] = useState([])
  const [activeAssignment, setActiveAssignment] = useState(null)

  useEffect(() => {
    getUpcomingAssignments()
      .then((data) => setAssignments(data.assignments || []))
      .catch(() => setAssignments([]))
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Auto-grow the input textarea with the content. Floored at 48px (h-12) so
  // it never renders shorter than the Send/Explore buttons beside it, capped
  // at 192px (max-h-48) to match the CSS cap below -- beyond that it scrolls
  // internally.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.max(48, Math.min(el.scrollHeight, 192))}px`
  }, [input])

  const handleSend = useCallback(async (override, assignmentIdOverride) => {
    const text = (override ?? input).trim()
    if (!text) return
    const assignmentId = assignmentIdOverride ?? activeAssignment?.id ?? null

    const userMessage = { role: 'user', content: text }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    // Feedback-mode responses stream in via SSE; concept/homework-help
    // responses stay the classic blocking JSON call. The server picks which
    // one via intent classification -- the client just reacts to whichever
    // one it gets. `assistantId` identifies the (possibly still-empty)
    // placeholder message deltas get appended into, added lazily on first
    // event so a non-streamed response never leaves a stray empty bubble.
    const assistantId = `${Date.now()}-${Math.random()}`
    let placeholderAdded = false
    const ensurePlaceholder = () => {
      if (placeholderAdded) return
      placeholderAdded = true
      setLoading(false)
      setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true, question: text }])
    }

    try {
      const result = await sendChatMessage({
        message: text,
        voiceEnabled,
        responseLanguage,
        assignmentId,
        onEvent: (event) => {
          if (event.type === 'delta') {
            ensurePlaceholder()
            setMessages(prev => prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + event.text } : m
            ))
          } else if (event.type === 'done') {
            setMessages(prev => prev.map((m) =>
              m.id === assistantId
                ? { ...m, streaming: false, sources: event.sources || [], directiveSources: event.directive_sources || [] }
                : m
            ))
          } else if (event.type === 'error') {
            ensurePlaceholder()
            setMessages(prev => prev.map((m) =>
              m.id === assistantId
                ? { ...m, streaming: false, error: true, content: m.content || event.message || 'Something went wrong.' }
                : m
            ))
          }
        },
      })

      if (!result.streamed) {
        const data = result.data
        const botMessage = {
          role: 'assistant',
          content: data.answer,
          audio: data.audio_base64,
          sources: data.sources,
          question: text,
        }

        setMessages(prev => [...prev, botMessage])

        if (voiceEnabled && data.audio_base64) {
          playAudio(data.audio_base64)
        }
      }
    } catch (error) {
      console.error('Error:', error)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, there was an error processing your request.',
        error: true
      }])
    } finally {
      setLoading(false)
    }
  }, [input, voiceEnabled, responseLanguage, activeAssignment])

  const handleGetHomeworkHelp = (assignment) => {
    setActiveAssignment(assignment)
    void handleSend(
      `I'm working on the ${assignment.name} assignment. Can you help me understand the rubric and what I need to do to get a top score?`,
      assignment.id,
    )
  }

  const playAudio = (base64Audio) => {
    if (audioRef.current) {
      audioRef.current.src = `data:audio/mpeg;base64,${base64Audio}`
      audioRef.current.play().catch(err => {
        console.log('Autoplay blocked:', err)
      })
    }
  }

  const handleExploreFromChat = (topic) => {
    const t = (topic ?? '').trim()
    if (!t) return
    setExploreSeed({ topic: t, nonce: Date.now() })
    setView('explore')
  }

  const handleAskInChat = useCallback((question) => {
    const q = (question ?? '').trim()
    if (!q) return
    setChatSeed({ question: q, nonce: Date.now() })
    setView('chat')
  }, [])

  // Seeded from Explore: auto-fill + auto-send once per nonce.
  useEffect(() => {
    if (chatSeed?.question) {
      void handleSend(chatSeed.question)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatSeed?.nonce])

  return (
    <div className="flex flex-col h-screen">
      {/* Navigation Bar */}
      <nav className="bg-[#34006f] shadow-[0_4px_12px_rgba(0,0,0,0.4)] relative z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <img src="/uw-logo.png" alt="UW" className="h-10 w-auto" />
              <span className="text-lg font-semibold text-white hidden sm:inline">Lecture Bot</span>

              {/* Chat / Explore view toggle -- anchored to the logo group
                  (a fixed reference point) rather than centered on or
                  packed against the right-hand controls, so it never
                  shifts position when the chat-only controls (language,
                  voice) appear/disappear on view switch. */}
              <div className="ml-4 flex rounded-lg bg-black/20 p-1">
                <button
                  onClick={() => setView('chat')}
                  className={`h-7 flex items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors ${
                    view === 'chat' ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                  }`}
                >
                  <ChatBubbleLeftRightIcon className="h-4 w-4" />
                  Chat
                </button>
                <button
                  onClick={() => setView('explore')}
                  className={`h-7 flex items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors ${
                    view === 'explore' ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                  }`}
                >
                  <Sparkles className="h-4 w-4" />
                  Explore
                </button>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {view === 'chat' && (
                <div className="flex rounded-lg bg-black/20 p-1" title="Reply language — you may type in either language">
                  <button
                    onClick={() => setResponseLanguage('en')}
                    className={`h-7 flex items-center rounded-md px-3 text-sm font-medium transition-colors ${
                      responseLanguage === 'en' ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                    }`}
                  >
                    English
                  </button>
                  <button
                    onClick={() => setResponseLanguage('zh')}
                    className={`h-7 flex items-center rounded-md px-3 text-sm font-medium transition-colors ${
                      responseLanguage === 'zh' ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                    }`}
                  >
                    中文
                  </button>
                </div>
              )}

              {view === 'chat' && (
                // Same rounded-lg bg-black/20 p-1 container as the language
                // toggle, so this button matches its height/vertical
                // alignment exactly rather than approximating it separately.
                <div className="flex rounded-lg bg-black/20 p-1">
                  <button
                    onClick={() => setVoiceEnabled(!voiceEnabled)}
                    className={`h-7 flex items-center justify-center rounded-md px-3 text-sm font-medium transition-colors ${
                      voiceEnabled ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                    }`}
                    title={voiceEnabled ? 'Voice: Chris (on) — click to mute' : 'Voice: Chris (off) — click to enable'}
                  >
                    {voiceEnabled ? (
                      <SpeakerWaveIcon className="h-4 w-4" />
                    ) : (
                      <SpeakerXMarkIcon className="h-4 w-4" />
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      {view === 'explore' ? (
        <ExploreCanvas
          seed={exploreSeed}
          onSeedConsumed={() => setExploreSeed(null)}
          onAskInChat={handleAskInChat}
        />
      ) : (
        <div className="flex-1 relative overflow-hidden">
          {/* Chat Messages */}
          <div className="absolute inset-0 overflow-y-auto p-4 space-y-4 pb-32">
            <div className="max-w-4xl mx-auto">
              {assignments.length > 0 && !activeAssignment && (
                <div className="mb-4 space-y-2">
                  {assignments.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => handleGetHomeworkHelp(a)}
                      className="flex w-full items-center gap-3 rounded-xl border border-[#9D4EDD]/50 bg-[#9D4EDD]/10 px-4 py-3 text-left hover:bg-[#9D4EDD]/20"
                    >
                      <NotebookPen size={18} className="shrink-0 text-[#E0B0FF]" />
                      <span className="flex-1 text-sm text-white">
                        <span className="font-semibold">{a.name}</span>
                        <span className="text-white/60"> — Due {a.due_display} · {a.points} pts</span>
                      </span>
                      <span className="shrink-0 text-xs font-medium text-[#E0B0FF]">Get homework help →</span>
                    </button>
                  ))}
                </div>
              )}

              {activeAssignment && (
                <div className="mb-4 flex items-center gap-2 rounded-xl border border-[#9D4EDD]/50 bg-[#9D4EDD]/10 px-4 py-2">
                  <NotebookPen size={16} className="shrink-0 text-[#E0B0FF]" />
                  <span className="flex-1 text-sm text-white/85">
                    Homework help active: <span className="font-semibold">{activeAssignment.name}</span>
                  </span>
                  <button
                    onClick={() => setActiveAssignment(null)}
                    title="Exit homework help mode"
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/60 hover:bg-white/10 hover:text-white"
                  >
                    <X size={13} /> Exit
                  </button>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={msg.id ?? idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-2xl rounded-2xl px-6 py-4 shadow-md ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-[#8938f6] to-[#b565ff] text-white'
                        : msg.error
                        ? 'bg-red-900 text-white'
                        : 'bg-gradient-to-br from-[rgba(15,15,15,0.95)] to-[rgba(45,45,45,0.95)] text-gray-100'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">
                      {msg.content}
                      {msg.streaming && (
                        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-white/60 align-middle" />
                      )}
                    </p>

                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      {msg.audio && voiceEnabled && (
                        <button
                          onClick={() => playAudio(msg.audio)}
                          className="text-sm text-white/70 hover:text-white"
                        >
                          🔊 Play audio
                        </button>
                      )}

                      {msg.role === 'assistant' && !msg.error && !msg.streaming && msg.question && (
                        <button
                          onClick={() => handleExploreFromChat(msg.question)}
                          title="Branch this topic visually on the Explore canvas"
                          className="inline-flex items-center gap-1 rounded-md border border-[#9D4EDD]/60 bg-[#9D4EDD]/15 px-2 py-0.5 text-xs font-medium text-[#E0B0FF] hover:bg-[#9D4EDD]/25"
                        >
                          <Sparkles size={12} />
                          Explore
                        </button>
                      )}
                    </div>

                    {msg.directiveSources && msg.directiveSources.length > 0 && (
                      <details className="mt-2 text-sm text-white/60">
                        <summary className="cursor-pointer hover:text-white/80">
                          🎯 Grading criteria referenced ({msg.directiveSources.length})
                        </summary>
                        <ul className="mt-2 space-y-1 pl-4">
                          {msg.directiveSources.map((source, i) => (
                            <li key={i} className="text-xs">{source}</li>
                          ))}
                        </ul>
                      </details>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <details className="mt-2 text-sm text-white/60">
                        <summary className="cursor-pointer hover:text-white/80">
                          📎 Sources ({msg.sources.length})
                        </summary>
                        <ul className="mt-2 space-y-1 pl-4">
                          {msg.sources.map((source, i) => (
                            <li key={i} className="text-xs">{source}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gradient-to-br from-[rgba(15,15,15,0.95)] to-[rgba(45,45,45,0.95)] rounded-2xl px-6 py-4">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                      <div className="w-2 h-2 bg-white/50 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input dock: centered on launch, animates down to a bottom bar
              once the conversation starts (hasMessages flips items-center
              to a bottom-hugging position; framer-motion's `layout` prop
              animates the resulting position change on the row itself). */}
          <div
            className={`absolute inset-x-0 flex justify-center px-4 pointer-events-none ${
              hasMessages
                ? 'bottom-0 border-t border-white/15 bg-black/20'
                : 'top-0 bottom-0 items-center'
            }`}
          >
            <motion.div
              layout
              transition={{ type: 'spring', stiffness: 260, damping: 28 }}
              className="w-full max-w-4xl py-4 pointer-events-auto"
            >
              {!hasMessages && (
                <p className="mb-4 text-center text-white/70">
                  Ask Professor Levine about the lectures, or paste your work for feedback
                </p>
              )}
              <div className="flex items-center space-x-3">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  placeholder="Ask Professor Levine about the lectures, or paste your work for feedback..."
                  rows={1}
                  className="flex-1 h-12 resize-none max-h-48 overflow-y-auto bg-white/10 border border-white/20 text-white placeholder-white/40 rounded-lg px-4 py-3 focus:outline-none focus:ring-1 focus:ring-white/40"
                  disabled={loading}
                  autoFocus
                />
                <button
                  onClick={() => handleSend()}
                  disabled={loading || !input.trim()}
                  className="h-12 flex items-center justify-center bg-white/15 hover:bg-white/25 border-2 border-white/30 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 rounded-lg font-medium transition-colors hover:underline"
                >
                  Send
                </button>
                <button
                  onClick={() => handleExploreFromChat(input)}
                  disabled={!input.trim()}
                  title="Open this topic on the Explore canvas"
                  className="h-12 inline-flex items-center gap-1.5 rounded-lg border border-[#9D4EDD]/60 bg-[#9D4EDD]/15 px-4 text-sm font-medium text-[#E0B0FF] hover:bg-[#9D4EDD]/25 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Sparkles size={15} />
                  <span className="hidden sm:inline">Explore</span>
                </button>
              </div>
            </motion.div>
          </div>
        </div>
      )}

      {/* Hidden audio element for playback */}
      <audio ref={audioRef} className="hidden" />
    </div>
  )
}

export default App
