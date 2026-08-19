import axios from 'axios'

export async function postExplore({ topic, parentPath = [], allowGeneralFallback = true, skipClarify = false }) {
  const response = await axios.post('/api/explore', {
    topic,
    parent_path: parentPath,
    allow_general_fallback: allowGeneralFallback,
    skip_clarify: skipClarify,
  })
  return response.data
}

export async function postChat({ message, voiceEnabled = false, responseLanguage = 'en', assignmentId = null }) {
  const response = await axios.post('/api/chat', {
    message,
    voice_enabled: voiceEnabled,
    response_language: responseLanguage,
    assignment_id: assignmentId,
  })
  return response.data
}

// POST /api/chat, but reads the response as either plain JSON (concept
// questions, homework-help) or SSE (feedback mode) depending on the
// Content-Type the server sends back -- the caller doesn't pick the mode,
// the server's intent classification does. onEvent(event) fires once per
// SSE frame ({type: 'delta'|'done'|'error', ...}) as it arrives.
export async function sendChatMessage({
  message,
  voiceEnabled = false,
  responseLanguage = 'en',
  assignmentId = null,
  onEvent = null,
}) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      voice_enabled: voiceEnabled,
      response_language: responseLanguage,
      assignment_id: assignmentId,
    }),
  })

  const contentType = response.headers.get('content-type') || ''

  if (!contentType.includes('text/event-stream')) {
    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}))
      const err = new Error(errBody.detail || `Request failed (${response.status})`)
      err.status = response.status
      throw err
    }
    const data = await response.json()
    return { streamed: false, data }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const frames = buffer.split('\n\n')
    buffer = frames.pop() // last element may be an incomplete frame

    for (const frame of frames) {
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        const event = JSON.parse(line.slice(6))
        onEvent?.(event)
      } catch (e) {
        console.warn('Failed to parse SSE frame:', frame, e)
      }
    }
  }

  return { streamed: true }
}

export async function getUpcomingAssignments() {
  const response = await axios.get('/api/assignments/upcoming')
  return response.data
}

export async function createBoard({ title, data }) {
  const response = await axios.post('/api/boards', { title, data })
  return response.data
}

export async function getBoard(boardId) {
  const response = await axios.get(`/api/boards/${boardId}`)
  return response.data
}

export async function listBoards() {
  const response = await axios.get('/api/boards')
  return response.data
}

export async function saveBoard(boardId, ownerToken, { title, data } = {}) {
  const response = await axios.post(`/api/boards/${boardId}/save`, {
    owner_token: ownerToken,
    title,
    data,
  })
  return response.data
}

export async function deleteBoard(boardId, ownerToken) {
  const response = await axios.post(`/api/boards/${boardId}/delete`, {
    owner_token: ownerToken,
  })
  return response.data
}
