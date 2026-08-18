export function isSegmentPreviewReady(segment) {
  return Boolean(
    segment
    && segment.image_status === 'completed'
    && segment.audio_status === 'completed'
    && segment.image_url
    && segment.audio_url,
  )
}

export function nextPreviewIndex(segments, currentIndex) {
  const nextIndex = Number(currentIndex) + 1
  if (!Array.isArray(segments) || nextIndex >= segments.length) return null
  return isSegmentPreviewReady(segments[nextIndex]) ? nextIndex : null
}
