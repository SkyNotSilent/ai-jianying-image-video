export function deriveTaskState({ task = {}, segments = [], exportState = null } = {}) {
  const rawStatus = task?.status || exportState?.status || 'completed'
  const segmentList = Array.isArray(segments) ? segments : []
  const hasSegmentEvidence = segmentList.length > 0
  const hasCheckpointEvidence = Boolean(task?.can_resume) || hasSegmentEvidence || Boolean(task?.script_text?.trim?.())
  const hasError = Boolean(task?.error)
  const hasFailedSegment = segmentList.some((segment) => segment.image_status === 'failed' || segment.audio_status === 'failed')
  const hasMissingAsset = segmentList.some((segment) => !segment.image_url || !segment.audio_url)
  const hasPreviewEvidence = Boolean(exportState)
  const previewValid = Boolean(exportState?.preview?.valid)
  const mp4Available = Boolean(exportState?.outputs?.mp4?.available)
  const draftAvailable = Boolean(exportState?.outputs?.draft?.available)

  if (rawStatus === 'pending' || rawStatus === 'processing') {
    return {
      key: 'processing',
      label: rawStatus === 'pending' ? '等待中' : '生成中',
      tone: 'info',
      actionLabel: '查看进度',
      canPreview: false,
      canExport: false,
      canRecover: true,
    }
  }

  if (rawStatus === 'interrupted' || (rawStatus === 'failed' && hasCheckpointEvidence)) {
    return {
      key: 'interrupted',
      label: rawStatus === 'failed' ? '失败可继续' : '生成已中断',
      tone: 'warning',
      actionLabel: '查看并继续',
      canPreview: hasSegmentEvidence,
      canExport: false,
      canRecover: true,
    }
  }

  if (rawStatus === 'failed') {
    return {
      key: 'recoverable_assets',
      label: '失败可恢复',
      tone: 'danger',
      actionLabel: '查看已保存素材',
      canPreview: true,
      canExport: false,
      canRecover: true,
    }
  }

  if (hasError || hasFailedSegment || hasMissingAsset) {
    return {
      key: 'recoverable_assets',
      label: '失败可恢复',
      tone: 'danger',
      actionLabel: '查看已保存素材',
      canPreview: true,
      canExport: hasSegmentEvidence || draftAvailable,
      canRecover: true,
    }
  }

  if (mp4Available || previewValid) {
    return {
      key: 'export_ready',
      label: mp4Available ? '可导出' : '预览可用',
      tone: 'success',
      actionLabel: '查看预览',
      canPreview: true,
      canExport: true,
      canRecover: true,
    }
  }

  if (hasPreviewEvidence && !previewValid) {
    return {
      key: 'completed',
      label: draftAvailable ? '素材已就绪' : '内容预览可用',
      tone: 'success',
      actionLabel: '查看预览',
      canPreview: true,
      canExport: hasSegmentEvidence || draftAvailable,
      canRecover: true,
    }
  }

  if (rawStatus === 'completed' && !hasSegmentEvidence) {
    return {
      key: 'completed',
      label: '已完成',
      tone: 'success',
      actionLabel: '查看预览',
      canPreview: true,
      canExport: true,
      canRecover: true,
    }
  }

  return {
    key: 'completed',
    label: '已完成',
    tone: 'success',
    actionLabel: '查看预览',
    canPreview: true,
    canExport: true,
    canRecover: true,
  }
}

export function ratioLabel(ratio) {
  const value = String(ratio || '16:9')
  return {
    '16:9': '16:9（横屏）',
    '9:16': '9:16（竖屏）',
    '1:1': '1:1（方形）',
    '3:4': '3:4（竖图）',
    '4:3': '4:3（横图）',
  }[value] || value
}

export function ratioClassName(ratio) {
  const value = String(ratio || '16:9')
  if (value === '9:16') return 'ratio-vertical'
  if (value === '1:1') return 'ratio-square'
  if (value === '3:4') return 'ratio-portrait'
  if (value === '4:3') return 'ratio-classic'
  return 'ratio-wide'
}
