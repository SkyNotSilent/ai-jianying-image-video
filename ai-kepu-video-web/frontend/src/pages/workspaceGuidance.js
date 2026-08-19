const STEP_DEFINITIONS = Object.freeze([
  { id: 'manuscript', label: '写文稿', description: '文稿已保存' },
  { id: 'planning', label: '生成预案', description: '生成文案、分镜和提示词' },
  { id: 'voice', label: '确认音色', description: '选择全片配音' },
  { id: 'visual', label: '确认画面', description: '检查分镜与画面描述' },
  { id: 'assets', label: '生成素材', description: '生成图片与配音' },
  { id: 'complete', label: '完成', description: '完成生产并预览导出' },
])

function finite(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, finite(value)))
}

function activeOperationStep(operation) {
  if (!operation || !['pending', 'running'].includes(operation.status)) return null
  if (operation.kind === 'finalize') return 5
  if (operation.kind === 'regenerate_prompt') return 1
  return 4
}

export function resolveWorkspaceStep(workspace = {}) {
  const operationStep = activeOperationStep(workspace.active_operation)
  if (operationStep !== null) return operationStep

  const stage = String(workspace.stage || '')
  if (stage === 'planning') return 1
  if (stage === 'awaiting_confirmation') return workspace.voice_confirmed && workspace.voice_type ? 3 : 2
  if (['generating_assets', 'repairing_assets'].includes(stage)) return 4
  if (['awaiting_finalization', 'finalizing'].includes(stage)) return 5
  if (stage === 'ready') {
    return workspace.recovery?.mode === 'update_stale_assets' ? 4 : 5
  }
  if (['interrupted', 'failed'].includes(stage)) {
    const mode = workspace.recovery?.mode
    if (['restart_planning', 'resume_planning'].includes(mode)) return 1
    if (['retry_assets', 'update_stale_assets'].includes(mode)) return 4
    if (['finalize', 'finalize_failed'].includes(mode)) return 5
    if (workspace.health?.missing_prompts) return 1
    if (workspace.voice_confirmed && workspace.voice_type) return 4
    return 2
  }
  return workspace.voice_confirmed && workspace.voice_type ? 3 : 1
}

function promptFraction(workspace) {
  const step = workspace.planning_step
  if (step === 'text_generation') return 0
  if (step === 'segmentation') return 0.3
  const total = Math.max(0, finite(workspace.progress?.prompts_total ?? workspace.segments_count))
  const ready = Math.max(0, finite(workspace.progress?.prompts_ready))
  if (!total) return step === 'image_prompt_generation' ? 0.4 : 0
  return 0.4 + 0.6 * clamp(ready / total)
}

function assetFraction(workspace) {
  const total = Math.max(0, finite(workspace.segments_count ?? workspace.segments?.length))
  if (!total) return 0
  const images = Math.max(0, finite(workspace.progress?.images_ready))
  const audio = Math.max(0, finite(workspace.progress?.audio_ready))
  return clamp((images + audio) / (total * 2))
}

function operationFraction(operation) {
  const total = Math.max(0, finite(operation?.total))
  if (!total) return 0
  return clamp((finite(operation?.completed) + finite(operation?.failed)) / total)
}

function overallProgress(workspace, currentStep) {
  if (workspace.stage === 'ready' && workspace.recovery?.mode !== 'update_stale_assets') return 100
  if (currentStep === 1) return 10 + 20 * promptFraction(workspace)
  if (currentStep === 2) return 35
  if (currentStep === 3) return 50
  if (currentStep === 4) return 55 + 35 * assetFraction(workspace)
  if (currentStep === 5) {
    if (workspace.stage === 'awaiting_finalization') return 92
    if (workspace.active_operation?.kind === 'finalize') return 92 + 7 * operationFraction(workspace.active_operation)
    return workspace.stage === 'ready' ? 100 : 92
  }
  return 0
}

export function deriveWorkspaceJourney(workspace = {}) {
  const currentStep = resolveWorkspaceStep(workspace)
  const percent = Math.round(clamp(overallProgress(workspace, currentStep), 0, 100))
  const complete = percent === 100
  const steps = STEP_DEFINITIONS.map((step, index) => ({
    ...step,
    state: complete || index < currentStep ? 'completed' : index === currentStep ? 'current' : 'pending',
  }))
  const hasProgressSample = currentStep === 4 && (
    finite(workspace.progress?.images_ready) + finite(workspace.progress?.audio_ready) > 0
  )
  const estimateLabel = hasProgressSample
    ? '剩余时间正在根据已完成素材估算'
    : currentStep < 4 && workspace.generation_estimate
      ? '素材阶段将显示动态估算'
      : '剩余时间正在估算'
  return { currentStep, percent, steps, estimateLabel }
}

const ASSET_LABELS = Object.freeze({ prompt: '提示词', image: '图片', audio: '配音' })

function targetFromSegment(segment, assetType, status) {
  const metadata = segment?.[`${assetType}_error_meta`] || segment?.[`${assetType}_error_meta_json`] || {}
  return {
    key: `${finite(segment?.segment_index)}:${assetType}`,
    segmentIndex: Math.max(0, finite(segment?.segment_index)),
    assetType,
    assetLabel: ASSET_LABELS[assetType],
    status,
    errorSource: {
      error_code: segment?.[`${assetType}_error_code`],
      error_meta: metadata,
    },
  }
}

export function segmentFailureTargets(segment = {}) {
  return ['prompt', 'image', 'audio']
    .filter(assetType => segment?.[`${assetType}_status`] === 'failed')
    .map(assetType => targetFromSegment(segment, assetType, 'failed'))
}

export function collectWorkspaceIssues(workspace = {}) {
  const segments = Array.isArray(workspace.segments) ? workspace.segments : []
  const failedByKey = new Map()
  const staleByKey = new Map()

  for (const segment of segments) {
    for (const target of segmentFailureTargets(segment)) failedByKey.set(target.key, target)
    for (const assetType of ['prompt', 'image', 'audio']) {
      const stale = segment?.[`${assetType}_status`] === 'stale'
        || (assetType === 'prompt' && segment?.prompt_needs_review)
      if (!stale) continue
      const target = targetFromSegment(segment, assetType, 'stale')
      staleByKey.set(target.key, target)
    }
  }

  const failures = [...failedByKey.values()].sort((a, b) => (
    a.segmentIndex - b.segmentIndex
    || ['prompt', 'image', 'audio'].indexOf(a.assetType) - ['prompt', 'image', 'audio'].indexOf(b.assetType)
  ))
  const stale = [...staleByKey.values()].filter(target => !failedByKey.has(target.key))
  const counts = { prompt: 0, image: 0, audio: 0 }
  failures.forEach(target => { counts[target.assetType] += 1 })

  return {
    failures,
    stale,
    counts,
    failureCount: failures.length,
    failedSegmentCount: new Set(failures.map(target => target.segmentIndex)).size,
  }
}

export function buildFailedRetryPayload(workspace = {}) {
  return {
    snapshot_key: String(workspace.snapshot_key || ''),
    scope: 'failed',
  }
}

export function partitionWorkspaceFailures(issues = {}) {
  const failures = Array.isArray(issues.failures) ? issues.failures : []
  return {
    prompts: failures.filter(target => target.assetType === 'prompt'),
    assets: failures.filter(target => target.assetType === 'image' || target.assetType === 'audio'),
  }
}
