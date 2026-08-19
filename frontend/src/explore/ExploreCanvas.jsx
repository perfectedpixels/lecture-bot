import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './explore.css'
import { AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { FolderOpen, Loader2, Save, Share2, Sparkles } from 'lucide-react'
import { createBoard, getBoard, listBoards, postExplore, saveBoard } from '../api/client'
import { CardChatModal } from './CardChatModal'
import { CardNode } from './CardNode'
import { ClarifyNode } from './ClarifyNode'

const nodeTypes = { card: CardNode, clarify: ClarifyNode }
const COL_W = 360
const ROW_H = 220
// Vertical breathing room between stacked cards in the same column. Card
// height varies a lot with content (a plain card renders well under 220px,
// one with citations and a directed-branch composer can top 400px), so a
// fixed ROW_H alone isn't enough to prevent overlap -- see the reflow effect
// below, which is what actually enforces this gap using each card's real
// measured height once React Flow has rendered it.
const CARD_GAP = 15
// Used only for the brief window before a freshly-added card has been
// measured (React Flow populates node.measured after its first paint) --
// close to the observed real range so the pre-measurement layout doesn't
// visibly jump much once the true height snaps in.
const FALLBACK_CARD_HEIGHT = 400

let _seq = 0
const genId = () => `n${Date.now().toString(36)}_${_seq++}`

const SNAPSHOT_KEY = 'lecture-bot-explore-board'

const EMPTY_SNAPSHOT = { nodes: [], edges: [], meta: {}, cursor: {}, seq: 0 }

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || fallback
}

// Ownership tokens live only in this browser's localStorage — the server
// never re-sends them after create. No token cached for a board means this
// browser isn't the one that created it (e.g. opened via someone else's
// share link), so Save/Delete-in-place aren't offered — only "save a copy".
const ownerTokenKey = (boardId) => `board-owner-token:${boardId}`
const getOwnerToken = (boardId) => {
  try {
    return localStorage.getItem(ownerTokenKey(boardId))
  } catch {
    return null
  }
}
const setOwnerToken = (boardId, token) => {
  try {
    localStorage.setItem(ownerTokenKey(boardId), token)
  } catch {
    /* best-effort */
  }
}

function CanvasInner({ seed, onSeedConsumed, onAskInChat }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [topic, setTopic] = useState('')
  const [starting, setStarting] = useState(false)
  const [busy, setBusy] = useState(0)
  const [error, setError] = useState(null)

  const metaRef = useRef({})
  const columnCursor = useRef({})
  const nodesRef = useRef([])
  nodesRef.current = nodes
  const edgesRef = useRef([])
  edgesRef.current = edges
  const { setCenter, fitView } = useReactFlow()

  const nextY = useCallback((col) => {
    if (columnCursor.current[col] === undefined) columnCursor.current[col] = 40
    const y = columnCursor.current[col]
    columnCursor.current[col] += ROW_H
    return y
  }, [])

  // Enforces a consistent CARD_GAP between stacked cards, using each card's
  // real rendered height (node.measured.height, populated by React Flow
  // after first paint) rather than the rough ROW_H estimate nextY() uses for
  // provisional placement. Re-runs on every nodes change, so it also keeps
  // cards from overlapping if one grows (e.g. expanding a clamped paragraph)
  // or shrinks (collapsing it back). Converges in 1-2 passes: it only
  // updates positions that actually need to move, so once a column is
  // correctly spaced this is a no-op and doesn't loop.
  useEffect(() => {
    const byColumn = new Map()
    for (const n of nodes) {
      const col = metaRef.current[n.id]?.columnIndex ?? 0
      if (!byColumn.has(col)) byColumn.set(col, [])
      byColumn.get(col).push(n)
    }

    let changed = false
    const nextPositions = new Map()
    for (const colNodes of byColumn.values()) {
      colNodes.sort((a, b) => a.position.y - b.position.y)
      let cursorY = colNodes[0]?.position.y ?? 40
      for (const n of colNodes) {
        if (Math.abs(n.position.y - cursorY) > 0.5) {
          nextPositions.set(n.id, cursorY)
          changed = true
        }
        cursorY += (n.measured?.height ?? FALLBACK_CARD_HEIGHT) + CARD_GAP
      }
    }

    if (changed) {
      setNodes((ns) => ns.map((n) => (nextPositions.has(n.id) ? { ...n, position: { ...n.position, y: nextPositions.get(n.id) } } : n)))
    }
  }, [nodes, setNodes])

  const focus = useCallback(
    (x, y) => {
      setCenter(x + 150, y + 120, { zoom: 0.85, duration: 400 })
      setTimeout(() => fitView({ padding: 0.25, duration: 500, maxZoom: 1 }), 80)
    },
    [setCenter, fitView],
  )

  const setNodeData = useCallback(
    (id, patch) =>
      setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))),
    [setNodes],
  )

  // --- per-card grounded chat modal ---------------------------------------
  const [expandedId, setExpandedId] = useState(null)

  const onOpenChat = useCallback((id) => {
    setExpandedId(id)
  }, [])

  const addCards = useCallback(
    (cards, parentId, parentPath) => {
      const parentMeta = metaRef.current[parentId]
      const col = (parentMeta?.columnIndex ?? 0) + 1
      const x = col * COL_W + 40
      let firstY = 0
      const newNodes = cards.map((card, i) => {
        const id = card.id || genId()
        const y = nextY(col)
        if (i === 0) firstY = y
        metaRef.current[id] = { columnIndex: col, path: [...parentPath, card.title] }
        return {
          id,
          type: 'card',
          position: { x, y },
          data: {
            card,
            branched: false,
            branching: false,
            onOpenChat,
            onDirectedBranch,
            onBranch,
            onDelete,
            onAskInChat,
          },
        }
      })
      setNodes((ns) => [...ns, ...newNodes])
      setEdges((es) =>
        newNodes.reduce(
          (acc, n) => addEdge({ id: `${parentId}-${n.id}`, source: parentId, target: n.id, animated: true }, acc),
          es,
        ),
      )
      if (newNodes.length) focus(x, firstY)
    },
    // onBranch/onDirectedBranch/onDelete are declared below as stable closures
    // (not deps) to avoid a temporal-dead-zone error here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [focus, nextY, onOpenChat, onAskInChat, setEdges, setNodes],
  )

  const addClarify = useCallback(
    (res, parentId, parentPath) => {
      const parentMeta = metaRef.current[parentId]
      const col = (parentMeta?.columnIndex ?? 0) + 1
      const x = col * COL_W + 40
      const y = nextY(col)
      const id = genId()
      metaRef.current[id] = { columnIndex: col, path: parentPath }
      const node = {
        id,
        type: 'clarify',
        position: { x, y },
        data: {
          topic: res.topic,
          summary: res.summary ?? '',
          options: res.options ?? [],
          branching: false,
          onRefine,
          onSkip,
        },
      }
      setNodes((ns) => [...ns, node])
      setEdges((es) => addEdge({ id: `${parentId}-${id}`, source: parentId, target: id, animated: true }, es))
      focus(x, y)
    },
    [focus, nextY, setEdges, setNodes],
  )

  const branch = useCallback(
    async (nodeId, topicText, path, skipClarify) => {
      setBusy((b) => b + 1)
      try {
        const res = await postExplore({ topic: topicText, parentPath: path.slice(0, -1), skipClarify })
        if (res.mode === 'clarify') addClarify(res, nodeId, path)
        else addCards(res.cards ?? [], nodeId, path)
      } catch (err) {
        setError(errorMessage(err, 'Explore failed'))
      } finally {
        setBusy((b) => b - 1)
      }
    },
    [addCards, addClarify],
  )

  const onBranch = useCallback(
    (id) => {
      const meta = metaRef.current[id]
      const node = nodesRef.current.find((n) => n.id === id)
      const card = node?.data?.card
      if (!meta || !card) return
      setNodeData(id, { branching: true })
      void branch(id, card.title, meta.path, false).finally(() =>
        setNodeData(id, { branching: false, branched: true }),
      )
    },
    [branch, setNodeData],
  )

  const onDirectedBranch = useCallback(
    (id, direction) => {
      const meta = metaRef.current[id]
      const node = nodesRef.current.find((n) => n.id === id)
      const card = node?.data?.card
      if (!meta || !card) return
      const refined = `${card.title} — ${direction}`
      setNodeData(id, { branching: true })
      void branch(id, refined, [...meta.path, refined], true).finally(() => setNodeData(id, { branching: false }))
    },
    [branch, setNodeData],
  )

  const onRefine = useCallback(
    (clarifyId, answer) => {
      const meta = metaRef.current[clarifyId]
      const node = nodesRef.current.find((n) => n.id === clarifyId)
      const baseTopic = node?.data?.topic || ''
      const refined = `${baseTopic} — ${answer}`
      setNodeData(clarifyId, { branching: true })
      void branch(clarifyId, refined, [...(meta?.path ?? []), refined], true).finally(() =>
        setNodeData(clarifyId, { branching: false }),
      )
    },
    [branch, setNodeData],
  )

  const onSkip = useCallback(
    (clarifyId) => {
      const meta = metaRef.current[clarifyId]
      const node = nodesRef.current.find((n) => n.id === clarifyId)
      const baseTopic = node?.data?.topic || ''
      setNodeData(clarifyId, { branching: true })
      void branch(clarifyId, baseTopic, [...(meta?.path ?? []), baseTopic], true).finally(() =>
        setNodeData(clarifyId, { branching: false }),
      )
    },
    [branch, setNodeData],
  )

  const descendants = useCallback((id) => {
    const out = new Set()
    const queue = [id]
    while (queue.length) {
      const cur = queue.shift()
      for (const e of edgesRef.current) {
        if (e.source === cur && !out.has(e.target)) {
          out.add(e.target)
          queue.push(e.target)
        }
      }
    }
    return out
  }, [])

  const onDelete = useCallback(
    (id) => {
      const desc = descendants(id)
      if (
        desc.size > 0 &&
        !window.confirm(`Delete this card and its ${desc.size} descendant card(s)? This can't be undone.`)
      ) {
        return
      }
      const remove = new Set([id, ...desc])
      setNodes((ns) => ns.filter((n) => !remove.has(n.id)))
      setEdges((es) => es.filter((e) => !remove.has(e.source) && !remove.has(e.target)))
      remove.forEach((rid) => delete metaRef.current[rid])
    },
    [descendants, setEdges, setNodes],
  )

  const start = useCallback(
    async (override) => {
      const t = (override ?? topic).trim()
      if (override !== undefined) setTopic(override)
      if (!t) return
      setStarting(true)
      setError(null)
      setNodes([])
      setEdges([])
      metaRef.current = {}
      columnCursor.current = {}
      // a fresh topic starts a new, unsaved board
      setBoardId(null)
      setBoardTitle('')
      setUrlBoard(null)
      const rootId = genId()
      try {
        const rootY = nextY(0)
        metaRef.current[rootId] = { columnIndex: 0, path: [t] }
        const rootCard = {
          id: rootId,
          title: t,
          paragraph: 'Your starting point. Branch to explore grounded facets.',
          concepts: [],
          grounded: true,
          citations: [],
          source_note: 'Starting point',
        }
        setNodes([
          {
            id: rootId,
            type: 'card',
            position: { x: 40, y: rootY },
            data: {
              card: rootCard,
              isRoot: true,
              branched: true,
              branching: true,
              onOpenChat,
              onDirectedBranch,
              onBranch,
              onDelete,
              onAskInChat,
            },
          },
        ])
        const res = await postExplore({ topic: t })
        if (res.mode === 'clarify') addClarify(res, rootId, [t])
        else addCards(res.cards ?? [], rootId, [t])
        setNodeData(rootId, { branching: false })
      } catch (err) {
        setError(errorMessage(err, 'Explore failed'))
        setNodeData(rootId, { branching: false })
      } finally {
        setStarting(false)
      }
    },
    [addCards, addClarify, nextY, onOpenChat, onDirectedBranch, onBranch, onDelete, onAskInChat, setEdges, setNodes, setNodeData, topic],
  )

  // Seeded from Chat: auto-start this topic once per nonce, then let the
  // parent know so it doesn't re-trigger on remount / view switches.
  useEffect(() => {
    if (seed?.topic) {
      void start(seed.topic)
      onSeedConsumed?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  // --- snapshot helpers (shared by localStorage autosave + server boards) --
  const buildSnapshot = useCallback(() => {
    const strip = (n) => {
      const d = n.data
      const data =
        n.type === 'clarify'
          ? { topic: d.topic, summary: d.summary, options: d.options }
          : { card: d.card, isRoot: d.isRoot, branched: d.branched, branching: false }
      return { id: n.id, type: n.type, position: n.position, data, hidden: n.hidden }
    }
    return {
      nodes: nodesRef.current.map(strip),
      edges: edgesRef.current,
      meta: { ...metaRef.current },
      cursor: { ...columnCursor.current },
      seq: _seq,
      savedAt: Date.now(),
    }
  }, [])

  const applySnapshot = useCallback(
    (snap) => {
      metaRef.current = snap.meta || {}
      columnCursor.current = snap.cursor || {}
      if (typeof snap.seq === 'number') _seq = Math.max(_seq, snap.seq)
      setNodes(
        (snap.nodes || []).map((n) => ({
          ...n,
          data:
            n.type === 'clarify'
              ? { ...n.data, onRefine, onSkip }
              : { ...n.data, onOpenChat, onDirectedBranch, onBranch, onDelete, onAskInChat },
        })),
      )
      setEdges(snap.edges || [])
    },
    [onBranch, onDelete, onDirectedBranch, onOpenChat, onAskInChat, onRefine, onSkip, setEdges, setNodes],
  )

  // --- load on mount: URL ?board= wins over localStorage -------------------
  const hydrated = useRef(false)
  useEffect(() => {
    const urlBoard = new URLSearchParams(window.location.search).get('board')
    async function init() {
      if (urlBoard) {
        await loadBoard(urlBoard)
      } else {
        try {
          const raw = localStorage.getItem(SNAPSHOT_KEY)
          if (raw) applySnapshot(JSON.parse(raw) || EMPTY_SNAPSHOT)
        } catch {
          /* ignore corrupt snapshot */
        }
      }
      hydrated.current = true
    }
    void init()
    // mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!hydrated.current || nodes.length === 0) return
    try {
      localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(buildSnapshot()))
    } catch {
      /* quota — best-effort */
    }
  }, [nodes, edges, buildSnapshot])

  const clearBoard = useCallback(() => {
    localStorage.removeItem(SNAPSHOT_KEY)
    setNodes([])
    setEdges([])
    metaRef.current = {}
    columnCursor.current = {}
    setTopic('')
    setBoardId(null)
    setBoardTitle('')
    setUrlBoard(null)
  }, [setEdges, setNodes])

  // --- shareable server boards ---------------------------------------------
  const [boardId, setBoardId] = useState(null)
  const [boardTitle, setBoardTitle] = useState('')
  const [boards, setBoards] = useState([])
  const [showBoards, setShowBoards] = useState(false)
  const [notice, setNotice] = useState(null)

  const setUrlBoard = useCallback((id) => {
    const url = new URL(window.location.href)
    if (id) url.searchParams.set('board', id)
    else url.searchParams.delete('board')
    window.history.replaceState({}, '', url.pathname + url.search + url.hash)
  }, [])

  const loadBoard = useCallback(
    async (id) => {
      try {
        const { board } = await getBoard(id)
        applySnapshot(board.data || EMPTY_SNAPSHOT)
        setBoardId(board.board_id)
        setBoardTitle(board.title)
        setUrlBoard(board.board_id)
        setShowBoards(false)
      } catch (err) {
        setError(errorMessage(err, 'Could not open board'))
      }
    },
    [applySnapshot, setUrlBoard],
  )

  // Returns the board_id actually saved to, so callers (e.g. shareLink) don't
  // need to re-read `boardId` state right after this — that would still be
  // the stale pre-await closure value on a first save.
  const saveCurrentBoard = useCallback(async () => {
    if (nodesRef.current.length === 0) return null
    const data = buildSnapshot()
    const cachedToken = boardId ? getOwnerToken(boardId) : null
    try {
      if (boardId && cachedToken) {
        const { board } = await saveBoard(boardId, cachedToken, { title: boardTitle, data })
        setBoardTitle(board.title)
        setNotice('Saved.')
        return boardId
      }
      // No board yet, or this browser doesn't hold the owner token for it
      // (opened via someone else's share link) — save a copy instead.
      const title = boardTitle || window.prompt('Name this board', topic || 'Untitled board') || 'Untitled board'
      const { board, owner_token } = await createBoard({ title, data })
      setOwnerToken(board.board_id, owner_token)
      setBoardId(board.board_id)
      setBoardTitle(board.title)
      setUrlBoard(board.board_id)
      setNotice(boardId ? 'Saved a copy (you opened someone else’s board).' : 'Saved.')
      return board.board_id
    } catch (err) {
      setError(errorMessage(err, 'Could not save board'))
      return null
    }
  }, [boardId, boardTitle, buildSnapshot, setUrlBoard, topic])

  const openBoardList = useCallback(async () => {
    setShowBoards((v) => !v)
    try {
      const { boards: list } = await listBoards()
      setBoards(list)
    } catch {
      /* ignore */
    }
  }, [])

  const shareLink = useCallback(async () => {
    const id = boardId && getOwnerToken(boardId) ? boardId : await saveCurrentBoard()
    if (!id) return
    const url = new URL(window.location.href)
    url.searchParams.set('board', id)
    try {
      await navigator.clipboard.writeText(url.toString())
      setNotice('Share link copied to clipboard.')
    } catch {
      setNotice(url.toString())
    }
  }, [boardId, saveCurrentBoard])

  return (
    <div className="lb-explore relative flex-1">
      <div className="absolute left-1/2 top-4 z-10 flex w-[min(640px,92vw)] -translate-x-1/2 items-center gap-2 rounded-xl border border-white/15 bg-black/40 px-3 py-2 shadow-lg backdrop-blur">
        <Sparkles size={16} className="text-[#E0B0FF]" />
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void start()}
          placeholder="Type a topic to explore (e.g. usability testing methods)…"
          className="flex-1 bg-transparent text-sm text-white placeholder-white/40 focus:outline-none"
        />
        <button
          type="button"
          disabled={starting || !topic.trim()}
          onClick={() => void start()}
          className="flex items-center gap-1 rounded-lg bg-white/15 border-2 border-white/30 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/25 hover:underline disabled:cursor-not-allowed disabled:opacity-40"
        >
          {starting ? <Loader2 size={14} className="animate-spin" /> : 'Explore'}
        </button>
        {nodes.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => void saveCurrentBoard()}
              className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
              title="Save this board"
            >
              <Save size={13} /> Save
            </button>
            <button
              type="button"
              onClick={() => void shareLink()}
              className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
              title="Copy a shareable link"
            >
              <Share2 size={13} /> Share
            </button>
            <button
              type="button"
              onClick={clearBoard}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-white/50 hover:bg-white/10 hover:text-white/80"
              title="Clear the canvas"
            >
              Clear
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => void openBoardList()}
          className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
          title="Open a saved board"
        >
          <FolderOpen size={13} /> Boards
        </button>
      </div>

      {(starting || busy > 0) && (
        <div className="absolute left-1/2 top-16 z-10 -translate-x-1/2 rounded-lg bg-black/60 px-3 py-1.5 text-xs text-white/80 shadow backdrop-blur">
          <span className="flex items-center gap-2">
            <Loader2 size={12} className="animate-spin" />
            Thinking… generating grounded cards{busy > 1 ? ` (${busy})` : ''}
          </span>
        </div>
      )}

      {showBoards && (
        <div className="absolute bottom-6 left-1/2 z-10 max-h-80 w-[min(560px,92vw)] -translate-x-1/2 overflow-auto rounded-xl border border-white/15 bg-black/70 p-2 shadow-xl backdrop-blur">
          {boards.length === 0 && (
            <p className="p-2 text-sm text-white/50">No saved boards yet.</p>
          )}
          {boards.map((b) => (
            <button
              key={b.board_id}
              type="button"
              onClick={() => void loadBoard(b.board_id)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-white/85 hover:bg-white/10"
            >
              <span className="font-medium">{b.title}</span>
              <span className="text-xs text-white/40">
                {b.updated_at ? new Date(b.updated_at).toLocaleDateString() : ''}
              </span>
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="absolute left-1/2 top-24 z-10 -translate-x-1/2 rounded-lg border border-red-800 bg-red-950 px-3 py-1.5 text-xs text-red-300 shadow">
          {error}
        </div>
      )}

      {notice && !error && (
        <div
          className="absolute left-1/2 top-24 z-10 -translate-x-1/2 cursor-pointer rounded-lg border border-[#9D4EDD]/50 bg-[#2f1654] px-3 py-1.5 text-xs text-[#E0B0FF] shadow"
          onClick={() => setNotice(null)}
          title="Dismiss"
        >
          {notice}
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        minZoom={0.2}
        maxZoom={1.5}
        fitView
      >
        <Background gap={22} size={1} color="rgba(255,255,255,0.08)" />
        <Controls showInteractive={false} />
      </ReactFlow>

      <AnimatePresence>
        {expandedId &&
          (() => {
            const node = nodes.find((n) => n.id === expandedId)
            const card = node?.data?.card
            if (!card) return null
            return (
              <CardChatModal
                key={expandedId}
                card={card}
                onClose={() => setExpandedId(null)}
                onAskInChat={onAskInChat}
              />
            )
          })()}
      </AnimatePresence>
    </div>
  )
}

export function ExploreCanvas({ seed, onSeedConsumed, onAskInChat }) {
  return (
    <ReactFlowProvider>
      <CanvasInner seed={seed} onSeedConsumed={onSeedConsumed} onAskInChat={onAskInChat} />
    </ReactFlowProvider>
  )
}
