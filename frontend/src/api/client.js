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
