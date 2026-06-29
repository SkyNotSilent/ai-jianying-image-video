const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'

function apiOrigin() {
  try {
    return new URL(API_BASE, window.location.origin).origin
  } catch (error) {
    return 'http://localhost:2002'
  }
}

export function normalizeMediaUrl(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (raw.startsWith('data:') || raw.startsWith('blob:')) return raw

  const mediaIndex = raw.indexOf('/media/')
  if (mediaIndex >= 0) {
    return `${apiOrigin()}${raw.slice(mediaIndex)}`
  }

  if (raw.startsWith('media/')) return `${apiOrigin()}/${raw}`
  if (raw.startsWith('/')) return `${apiOrigin()}${raw}`
  return raw
}
