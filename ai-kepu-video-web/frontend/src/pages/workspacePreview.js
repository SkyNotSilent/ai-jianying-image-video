export function isSegmentPreviewReady(segment) {
  return Boolean(
    segment
    && ['completed', 'stale'].includes(segment.image_status)
    && ['completed', 'stale'].includes(segment.audio_status)
    && segment.image_url
    && segment.audio_url,
  )
}

export function areAllSegmentAssetsReady(segments) {
  return Boolean(
    Array.isArray(segments)
    && segments.length
    && segments.every(segment => (
      segment?.image_status === 'completed'
      && segment?.audio_status === 'completed'
      && segment?.image_url
      && segment?.audio_url
    )),
  )
}

export function deriveWorkspaceControls(workspace = {}) {
  const segments = Array.isArray(workspace.segments) ? workspace.segments : []
  const isRecoverable = Boolean(
    workspace.recovery?.allowed
    || ['interrupted', 'failed', 'awaiting_finalization'].includes(workspace.stage),
  )
  const allAssetsReady = areAllSegmentAssetsReady(segments)
  const issueCount = segments.reduce((count, segment) => (
    count
    + (segment.image_status === 'completed' && segment.image_url ? 0 : 1)
    + (segment.audio_status === 'completed' && segment.audio_url ? 0 : 1)
  ), 0)
  const recoveryLabel = workspace.recovery?.label || (
    !segments.length
      ? '重新开始生成'
      : allAssetsReady
        ? '完成生产并进入预览'
        : `重试 ${issueCount} 个缺失或失败素材`
  )
  const recoverySummary = workspace.recovery?.description || (
    !segments.length
      ? '生成在文案阶段中断，可从原始内容重新开始'
      : `图片 ${workspace.progress?.images_ready || 0}/${segments.length} · 配音 ${workspace.progress?.audio_ready || 0}/${segments.length}${allAssetsReady ? ' · 素材齐全，待完成生产' : ` · ${issueCount} 项待重试`}`
  )

  return {
    isRecoverable,
    canResume: Boolean(isRecoverable && (workspace.recovery?.allowed ?? workspace.can_resume)),
    recoveryLabel,
    recoverySummary,
    canEnterExport: Boolean(workspace.capabilities?.enter_export ?? allAssetsReady),
    canRenderFullVideo: Boolean(
      workspace.capabilities?.full_video ?? (workspace.stage === 'ready' && allAssetsReady),
    ),
  }
}

export function recoveryActionForWorkspace(workspace = {}) {
  const mode = workspace.recovery?.mode
  if (mode === 'retry_assets') return 'retry_assets'
  if (mode === 'update_stale_assets') return 'update_stale_assets'
  if (mode === 'finalize' || mode === 'finalize_failed') return 'finalize'
  return 'resume_planning'
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
