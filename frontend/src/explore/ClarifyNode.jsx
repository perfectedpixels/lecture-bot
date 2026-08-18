import { Handle, Position } from '@xyflow/react'
import { motion } from 'framer-motion'
import { HelpCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'

export function ClarifyNode({ id, data }) {
  const [own, setOwn] = useState('')

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className="relative w-80 rounded-2xl border border-amber-400/40 shadow-lg bg-gradient-to-br from-[rgba(15,15,15,0.95)] to-[rgba(45,45,45,0.95)]"
    >
      {data.branching && (
        <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 rounded-2xl bg-black/70 text-sm text-white/90">
          <Loader2 size={16} className="animate-spin" />
          Exploring…
        </div>
      )}

      <Handle type="target" position={Position.Left} />

      <div className="flex items-center gap-2 rounded-t-2xl border-b border-white/10 px-3 py-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-400">
          <HelpCircle size={16} color="#1a0033" />
        </span>
        <span className="text-xs font-medium text-amber-300">Needs focus</span>
      </div>

      <div className="px-3 py-3">
        <p className="text-sm text-white/75">
          {data.summary || `"${data.topic}" is broad — pick a direction to focus the lecture material.`}
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {(data.options || []).map((opt) => (
            <button
              key={opt}
              type="button"
              className="nodrag rounded-full border border-[#9D4EDD]/60 bg-[#9D4EDD]/15 px-3 py-1 text-xs text-[#E0B0FF] hover:bg-[#9D4EDD]/25"
              onClick={() => data.onRefine(id, opt)}
            >
              {opt}
            </button>
          ))}
        </div>

        <div className="nodrag mt-3 flex items-center gap-1">
          <input
            value={own}
            onChange={(e) => setOwn(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && own.trim()) data.onRefine(id, own.trim())
            }}
            placeholder="Or type your own angle…"
            className="flex-1 rounded-md bg-black/30 border border-white/10 px-2 py-1 text-xs text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-[#9D4EDD]"
          />
        </div>
      </div>

      <div className="nodrag flex justify-end border-t border-white/10 px-3 py-2">
        <button
          type="button"
          onClick={() => data.onSkip(id)}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-white/50 hover:bg-white/10 hover:text-white/80"
        >
          Explore generally anyway
        </button>
      </div>

      <Handle type="source" position={Position.Right} />
    </motion.div>
  )
}
