import { Handle, Position } from '@xyflow/react'
import { motion } from 'framer-motion'
import { Expand, Loader2, MessageSquare, Plus, SendHorizonal, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { conceptVisual } from './conceptVisual'

export function CardNode({ id, data }) {
  const card = data.card
  const grounded = card.grounded
  const visual = conceptVisual(card.concepts, grounded)
  const Icon = visual.icon
  const cites = card.citations ?? []
  const rootRef = useRef(null)
  const [draft, setDraft] = useState('')
  const [expanded, setExpanded] = useState(false)

  const originRect = () => {
    const r = rootRef.current?.getBoundingClientRect()
    return r
      ? { top: r.top, left: r.left, width: r.width, height: r.height }
      : { top: 0, left: 0, width: 300, height: 220 }
  }

  const sendDraft = () => {
    const t = draft.trim()
    if (!t) return
    setDraft('')
    data.onDirectedBranch(id, t)
  }

  return (
    <motion.div
      ref={rootRef}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className={`relative w-80 rounded-2xl border shadow-lg bg-gradient-to-br from-[rgba(15,15,15,0.95)] to-[rgba(45,45,45,0.95)] ${
        data.isRoot ? 'border-[#9D4EDD]' : 'border-white/15'
      }`}
      style={{ borderLeftColor: visual.color, borderLeftWidth: 3 }}
    >
      {data.branching && (
        <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 rounded-2xl bg-black/70 text-sm text-white/90">
          <Loader2 size={16} className="animate-spin" />
          Exploring branches…
        </div>
      )}

      <Handle type="target" position={Position.Left} />

      <div className="flex items-center gap-2 rounded-t-2xl border-b border-white/10 px-3 py-2">
        <span
          className="flex h-7 w-7 items-center justify-center rounded-lg"
          style={{ background: visual.color }}
        >
          <Icon size={16} color="#1a0033" />
        </span>
        <span className="text-xs font-medium" style={{ color: visual.color }}>
          {grounded ? visual.label : 'General knowledge'}
        </span>
        <span className="ml-auto flex items-center gap-1">
          {data.onAskInChat && (
            <button
              type="button"
              className="nodrag rounded-md p-1 text-white/60 hover:bg-white/10 hover:text-white"
              title="Continue this in Chat"
              onClick={() => data.onAskInChat(card.title)}
            >
              <MessageSquare size={14} />
            </button>
          )}
          <button
            type="button"
            className="nodrag rounded-md p-1 text-white/60 hover:bg-white/10 hover:text-white"
            title="Open the full grounded answer & chat"
            onClick={() => data.onOpenChat(id, originRect())}
          >
            <Expand size={14} />
          </button>
          {!data.isRoot && (
            <button
              type="button"
              className="nodrag rounded-md p-1 text-white/60 hover:bg-red-900/60 hover:text-red-300"
              title="Delete this card (and its branch)"
              onClick={() => data.onDelete(id)}
            >
              <X size={14} />
            </button>
          )}
        </span>
      </div>

      <div className="px-3 py-3">
        <h3 className="mb-1 text-sm font-semibold text-white">{card.title}</h3>
        <p
          className={`nodrag lb-card-para cursor-pointer text-sm text-white/75 ${
            expanded ? '' : 'is-clamped'
          }`}
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? 'Click to collapse' : 'Click to expand'}
        >
          {card.paragraph}
        </p>

        {!grounded && (
          <span className="mt-2 inline-block rounded-full bg-white/10 px-2 py-0.5 text-xs text-white/70">
            {card.source_note}
          </span>
        )}

        {cites.length > 0 && (
          <details className="nodrag mt-2 text-xs text-white/50">
            <summary className="cursor-pointer hover:text-white/80">
              Sources ({cites.length})
            </summary>
            <ul className="mt-1 space-y-1 pl-3">
              {cites.map((c, i) => (
                <li key={i}>
                  <span className="font-medium text-white/70">{c.label || `Source ${i + 1}`}</span>
                  {c.excerpt && <span className="block text-white/40">{c.excerpt}</span>}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {/* Inline directed-branch composer (send-only, no label). */}
      <div className="nodrag flex items-center gap-1 border-t border-white/10 px-3 py-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendDraft()}
          placeholder="Direct a new branch…"
          className="flex-1 rounded-md bg-black/30 border border-white/10 px-2 py-1 text-xs text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-[#9D4EDD]"
        />
        <button
          type="button"
          disabled={!draft.trim() || data.branching}
          onClick={sendDraft}
          className="rounded-md p-1.5 text-[#E0B0FF] hover:bg-white/10 disabled:opacity-30"
          title="Sprout a branch in this direction"
        >
          <SendHorizonal size={14} />
        </button>
      </div>

      <div className="flex justify-end rounded-b-2xl px-3 pb-2">
        <button
          type="button"
          disabled={data.branched || data.branching}
          onClick={() => data.onBranch(id)}
          className="nodrag flex items-center gap-1 rounded-lg bg-white/15 border-2 border-white/30 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/25 hover:underline disabled:cursor-not-allowed disabled:opacity-40"
        >
          {data.branching ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
          {data.branching ? 'Branching…' : data.branched ? 'Branched' : 'Branch'}
        </button>
      </div>

      <Handle type="source" position={Position.Right} />
    </motion.div>
  )
}
