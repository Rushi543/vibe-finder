const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function readJson(response) {
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? await response.json() : null

  if (!response.ok) {
    throw new Error(payload?.detail || 'Request failed')
  }

  return payload
}

export function buildGithubConnectUrl(userId, label) {
  const params = new URLSearchParams({
    user_id: userId,
    label,
  })
  return `${API_URL}/auth/github/start?${params.toString()}`
}

export async function connectAnilist(userId, anilistUsername, label) {
  const response = await fetch(`${API_URL}/anilist/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      anilist_username: anilistUsername,
      label,
    }),
  })
  return readJson(response)
}

export async function getUser(userId) {
  const response = await fetch(`${API_URL}/users/${encodeURIComponent(userId)}`)
  return readJson(response)
}

export async function getUmap() {
  const response = await fetch(`${API_URL}/umap`)
  return readJson(response)
}

export async function getMatches(userId, topK = 5) {
  const response = await fetch(`${API_URL}/matches/${encodeURIComponent(userId)}?top_k=${topK}`)
  return readJson(response)
}

export async function getWeightedMatches(userId, weights, topK = 5) {
  const response = await fetch(`${API_URL}/matches/weighted`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, weights, top_k: topK }),
  })
  return readJson(response)
}

export async function connectSteam(userId, steamIdentifier, label) {
  const response = await fetch(`${API_URL}/steam/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      steam_identifier: steamIdentifier,
      label,
    }),
  })
  return readJson(response)
}
