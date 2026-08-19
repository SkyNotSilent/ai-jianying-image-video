const STORAGE_KEY = 'insightcut:project-drafts'

export const visualStyles = [
  { value: '电影质感', label: '电影质感', description: '真实光影与镜头叙事', image: '/styles/电影质感.jpg' },
  { value: '吉卜力', label: '吉卜力', description: '温暖手绘与自然色彩', image: '/styles/吉卜力.webp' },
  { value: '3D动画', label: '3D 动画', description: '立体角色与明快质感', image: '/styles/3D动画.webp' },
  { value: '毛毡风', label: '毛毡风', description: '柔软材质与微缩场景', image: '/styles/毛毡风格.webp' },
  { value: '油彩画', label: '油彩画', description: '厚重笔触与艺术色块', image: '/styles/油彩画.jpg' },
  { value: '国风', label: '国风', description: '东方构图与水墨意境', image: '/styles/国风.webp' },
]

export const projectCovers = [
  '/reference-assets/hq-coastal-boy.jpg',
  '/reference-assets/clean-brain-reading.jpg',
  '/reference-assets/clean-ink-mountain.jpg',
  '/reference-assets/clean-study-boy.jpg',
  '/reference-assets/clean-future-city.jpg',
  '/reference-assets/clean-green-leaf.jpg',
  '/reference-assets/clean-girl-study.jpg',
  '/reference-assets/clean-astronaut-moon.jpg',
  '/reference-assets/clean-city-street.jpg',
  '/reference-assets/clean-data-wave.jpg',
  '/reference-assets/clean-sail-sunset.jpg',
  '/reference-assets/clean-neural-brain.jpg',
]

export const ratioOptions = ['16:9', '9:16', '3:4']

export const textStyles = ['知识科普', '温暖感人', '专业严谨', '轻松口语', '观点犀利']

export function createDraft(overrides = {}) {
  const now = new Date().toISOString()
  const draft = {
    draft_id: `draft_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: '',
    input_mode: 'script',
    theme: '',
    manuscript: '',
    length: 300,
    ratio: '16:9',
    visual_style: '吉卜力',
    text_style: '知识科普',
    voice_type: '',
    voice_name: '',
    voice_speed: 1,
    subtitle_enabled: true,
    created_task_id: '',
    created_at: now,
    updated_at: now,
    ...overrides,
  }
  draft.ratio = normalizeDraftRatio(draft.ratio)
  draft.visual_style = normalizeVisualStyle(draft.visual_style)
  saveDraft(draft)
  return draft
}

export function listDrafts() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const drafts = raw ? JSON.parse(raw) : []
    return Array.isArray(drafts)
      ? drafts
          .map((draft) => ({
            ...draft,
            ratio: normalizeDraftRatio(draft.ratio),
            visual_style: normalizeVisualStyle(draft.visual_style),
          }))
          .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
      : []
  } catch (error) {
    console.warn('读取本地草稿失败', error)
    return []
  }
}

export function getDraft(draftId) {
  return listDrafts().find((draft) => draft.draft_id === draftId) || null
}

export function getLatestDraft() {
  return listDrafts()[0] || null
}

export function saveDraft(draft) {
  const drafts = listDrafts()
  const normalized = {
    ...draft,
    ratio: normalizeDraftRatio(draft.ratio),
    visual_style: normalizeVisualStyle(draft.visual_style),
    updated_at: new Date().toISOString(),
  }
  const index = drafts.findIndex((item) => item.draft_id === normalized.draft_id)
  if (index >= 0) drafts[index] = normalized
  else drafts.unshift(normalized)
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts))
  return normalized
}

function normalizeDraftRatio(ratio) {
  return ratioOptions.includes(ratio) ? ratio : '16:9'
}

function normalizeVisualStyle(style) {
  const legacyMap = {
    '毛毡风格': '毛毡风',
    '科技感': '电影质感',
    '写实风格': '电影质感',
  }
  const value = legacyMap[style] || style
  return visualStyles.some((item) => item.value === value) ? value : '电影质感'
}

export function updateDraft(draftId, patch) {
  const current = getDraft(draftId)
  if (!current) return null
  return saveDraft({ ...current, ...patch })
}

export function deleteDraft(draftId) {
  const next = listDrafts().filter((draft) => draft.draft_id !== draftId)
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function manuscriptText(draft) {
  if (draft?.input_mode === 'theme') return String(draft?.theme || '').trim()
  return String(draft?.manuscript || '').trim()
}

export function formatLocalTime(value) {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function estimateDuration(text, speed = 1) {
  const count = String(text || '').replace(/\s+/g, '').length
  if (!count) return '00:00'
  const normalizedSpeed = Number.isFinite(Number(speed)) ? Math.max(0.5, Number(speed)) : 1
  const seconds = Math.max(8, Math.round(count / 4.2 / normalizedSpeed))
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

export function estimateSegments(text) {
  const count = String(text || '').replace(/\s+/g, '').length
  if (!count) return 0
  return Math.max(1, Math.ceil(count / 80))
}
