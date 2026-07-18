const promptGuidance = '画面要求：主体清晰、风格统一、适合知识解说视频，构图留出字幕安全区。'

export function sortSegmentsByIndex(segments) {
  return [...(Array.isArray(segments) ? segments : [])].sort(
    (left, right) => Number(left?.segment_index ?? 0) - Number(right?.segment_index ?? 0),
  )
}

export function getSegmentAssetState(segment = {}) {
  if (segment.image_status === 'failed') return { label: '图片失败', tone: 'danger' }
  if (segment.audio_status === 'failed') return { label: '配音失败', tone: 'danger' }
  if (!segment.image_url || !segment.audio_url) return { label: '素材缺失', tone: 'warning' }
  return { label: '已生成', tone: 'success' }
}

export function getSegmentDraftSnapshot(taskId, segment = {}) {
  const text = segment?.text || ''
  const imagePrompt = segment?.image_prompt || ''
  const identity = segment?.id ?? ''
  const index = segment?.segment_index ?? ''
  return {
    key: `${taskId || ''}:${identity}:${index}:${text}:${imagePrompt}`,
    text,
    imagePrompt,
  }
}

export function isTaskLoadPending({ loading, loadError, loadedTaskId, taskId }) {
  return Boolean(loading || (!loadError && loadedTaskId !== taskId))
}

export function createTaskRequestGuard(initialTaskId) {
  let activeTaskId = initialTaskId
  let generation = 0

  return {
    begin(taskId = activeTaskId) {
      return { taskId, generation }
    },
    changeTask(taskId) {
      if (taskId !== activeTaskId) {
        activeTaskId = taskId
        generation += 1
      }
    },
    accepts(token) {
      return token?.taskId === activeTaskId && token?.generation === generation
    },
  }
}

export function appendPromptGuidance(value) {
  const prompt = String(value || '').trim()
  if (prompt.includes(promptGuidance)) return prompt
  return [prompt, promptGuidance].filter(Boolean).join('\n')
}

export function normalizeSubtitleText(value) {
  const compact = String(value || '').replace(/\s+/g, ' ').trim()
  const clean = compact
    .replace(/^[。！？!?…，,；;、：:“”"‘’'「」『』《》〈〉]+/u, '')
    .replace(/[。！？!?…，,；;、：:“”"‘’'「」『』《》〈〉\s]+$/u, '')
  return clean || compact
}

export function subtitleFontSize(text, ratio) {
  const units = Array.from(text || '').reduce((sum, char) => {
    if (/\s/.test(char)) return sum + 0.35
    return sum + (char.charCodeAt(0) < 128 ? 0.55 : 1)
  }, 0)
  const safeUnits = ratio === '9:16' ? 18 : ratio === '3:4' ? 23 : 34
  const baseSize = 16
  if (!units || units <= safeUnits) return baseSize
  return Math.max(11, Math.floor((baseSize * safeUnits) / units))
}

export function secondsToLabel(value) {
  const seconds = Math.max(0, Math.round(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

export function segmentDuration(segment) {
  return Number(segment?.duration) || 7
}
