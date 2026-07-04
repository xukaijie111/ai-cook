const BASE = '/api'

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const detail = data.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || data.message || `请求失败 ${resp.status}`
    throw new Error(msg)
  }
  return data
}

export const api = {
  listDishes: () => request('/dishes'),
  getDish: (id) => request(`/dishes/${id}`),
  createDish: (body) => request('/dishes', { method: 'POST', body: JSON.stringify(body) }),
  deleteDish: (id) => request(`/dishes/${id}`, { method: 'DELETE' }),
  seedDishes: () => request('/dishes/seed', { method: 'POST' }),
  generatePrompt: (dishId) => request(`/dishes/${dishId}/prompts`, { method: 'POST' }),
  deletePrompt: (promptId) => request(`/prompts/${promptId}`, { method: 'DELETE' }),
  listVideos: (promptId) => request(`/prompts/${promptId}/videos`),
  createVideo: (promptId) => request(`/dishes/prompts/${promptId}/videos`, { method: 'POST' }),
  getVideo: (videoId) => request(`/videos/${videoId}`),
  deleteVideo: (videoId) => request(`/videos/${videoId}`, { method: 'DELETE' }),
}
