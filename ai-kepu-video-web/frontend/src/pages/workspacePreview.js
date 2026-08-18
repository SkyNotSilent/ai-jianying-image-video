export function isSegmentPreviewReady(segment) {
  return Boolean(
    segment
    && segment.image_status === 'completed'
    && segment.audio_status === 'completed'
    && segment.image_url
    && segment.audio_url,
  )
}

export function areAllSegmentAssetsReady(segments) {
  return Boolean(
    Array.isArray(segments)
    && segments.length
    && segments.every(isSegmentPreviewReady),
  )
}

export function nextPreviewIndex(segments, currentIndex) {
  const nextIndex = Number(currentIndex) + 1
  if (!Array.isArray(segments) || nextIndex >= segments.length) return null
  return isSegmentPreviewReady(segments[nextIndex]) ? nextIndex : null
}

export function previewPlaybackStartIndex(segments, selectedIndex, endedNaturally) {
  if (!Array.isArray(segments) || !segments.length) return null
  if (endedNaturally) return 0
  return Math.max(0, Math.min(Number(selectedIndex) || 0, segments.length - 1))
}
