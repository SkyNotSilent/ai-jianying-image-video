export function resolveApiDownloadUrl(apiBase, value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) return raw
  const base = String(apiBase || '').replace(/\/+$/, '')
  return `${base}${raw.startsWith('/') ? '' : '/'}${raw}`
}

export function materialPackageSummary(materials = {}) {
  const segmentCount = Math.max(0, Number(materials.segment_count) || 0)
  const imageCount = Math.max(0, Number(materials.image_count) || 0)
  const audioCount = Math.max(0, Number(materials.audio_count) || 0)
  const missingImageCount = Array.isArray(materials.missing_image_orders)
    ? materials.missing_image_orders.length
    : Math.max(0, segmentCount - imageCount)
  const missingAudioCount = Array.isArray(materials.missing_audio_orders)
    ? materials.missing_audio_orders.length
    : Math.max(0, segmentCount - audioCount)
  const available = Boolean(materials.available && imageCount + audioCount > 0)
  const complete = Boolean(available && materials.complete)
  const detail = `${imageCount} 张图片 · ${audioCount} 段音频 · ${segmentCount} 个分镜`
  const missingParts = []
  if (missingImageCount) missingParts.push(`缺少 ${missingImageCount} 张图片`)
  if (missingAudioCount) missingParts.push(`缺少 ${missingAudioCount} 段音频`)
  return {
    available,
    complete,
    detail,
    statusLabel: !available ? '暂无素材' : complete ? '素材完整' : '部分素材',
    warning: missingParts.length ? `${missingParts.join('、')}，将下载当前已有素材。` : '',
  }
}
