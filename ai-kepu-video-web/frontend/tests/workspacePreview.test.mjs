import test from 'node:test'
import assert from 'node:assert/strict'

import {
  areAllSegmentAssetsReady,
  deriveWorkspaceControls,
  isSegmentPreviewReady,
  nextPreviewIndex,
  previewPlaybackStartIndex,
  recoveryActionForWorkspace,
} from '../src/pages/workspacePreview.js'

const readySegment = index => ({
  segment_index: index,
  image_status: 'completed',
  audio_status: 'completed',
  image_url: `/media/segment_${index}.png`,
  audio_url: `/media/segment_${index}.wav`,
})

test('continuous preview advances only to the immediately following ready segment', () => {
  const segments = [readySegment(0), readySegment(1)]

  assert.equal(isSegmentPreviewReady(segments[0]), true)
  assert.equal(nextPreviewIndex(segments, 0), 1)
  assert.equal(nextPreviewIndex(segments, 1), null)
})

test('continuous preview stops instead of skipping a segment with missing media', () => {
  const segments = [
    readySegment(0),
    { ...readySegment(1), image_url: '', image_status: 'pending' },
    readySegment(2),
  ]

  assert.equal(isSegmentPreviewReady(segments[1]), false)
  assert.equal(nextPreviewIndex(segments, 0), null)
})

test('a naturally completed continuous preview restarts from the first segment', () => {
  const segments = [readySegment(0), readySegment(1), readySegment(2)]

  assert.equal(previewPlaybackStartIndex(segments, 2, true), 0)
  assert.equal(previewPlaybackStartIndex(segments, 1, false), 1)
})

test('export readiness requires every segment to have both persisted media files', () => {
  const complete = [readySegment(0), readySegment(1)]
  const missingImage = [
    readySegment(0),
    { ...readySegment(1), image_url: '', image_status: 'failed' },
  ]

  assert.equal(areAllSegmentAssetsReady(complete), true)
  assert.equal(areAllSegmentAssetsReady(missingImage), false)
  assert.equal(areAllSegmentAssetsReady([]), false)
})

test('workspace controls cover planning restart, partial retry, finalization, and ready delivery', () => {
  assert.deepEqual(deriveWorkspaceControls({
    stage: 'interrupted',
    can_resume: true,
    segments: [],
  }), {
    isRecoverable: true,
    canResume: true,
    recoveryLabel: '重新开始生成',
    recoverySummary: '生成在文案阶段中断，可从原始内容重新开始',
    canEnterExport: false,
    canRenderFullVideo: false,
  })

  const partial = deriveWorkspaceControls({
    stage: 'interrupted',
    can_resume: true,
    segments: [readySegment(0), { ...readySegment(1), image_status: 'failed', image_url: '' }],
  })
  assert.equal(partial.recoveryLabel, '重试 1 个缺失或失败素材')
  assert.equal(partial.canEnterExport, false)

  const finalize = deriveWorkspaceControls({
    stage: 'awaiting_finalization',
    can_resume: true,
    segments: [readySegment(0)],
    recovery: { label: '完成生产并进入预览', description: '素材齐全，待完成草稿' },
    capabilities: { enter_export: true, full_video: false },
  })
  assert.equal(finalize.recoveryLabel, '完成生产并进入预览')
  assert.equal(finalize.isRecoverable, true)
  assert.equal(finalize.canEnterExport, true)
  assert.equal(finalize.canRenderFullVideo, false)

  const ready = deriveWorkspaceControls({
    stage: 'ready',
    can_resume: false,
    segments: [readySegment(0)],
    capabilities: { enter_export: true, full_video: true },
  })
  assert.equal(ready.isRecoverable, false)
  assert.equal(ready.canRenderFullVideo, true)
})

test('workspace recovery actions never route asset repair through task resume', () => {
  assert.equal(recoveryActionForWorkspace({ recovery: { mode: 'retry_assets' } }), 'retry_assets')
  assert.equal(recoveryActionForWorkspace({ recovery: { mode: 'update_stale_assets' } }), 'update_stale_assets')
  assert.equal(recoveryActionForWorkspace({ recovery: { mode: 'finalize' } }), 'finalize')
  assert.equal(recoveryActionForWorkspace({ recovery: { mode: 'finalize_failed' } }), 'finalize')
  assert.equal(recoveryActionForWorkspace({ recovery: { mode: 'resume_planning' } }), 'resume_planning')
})

test('stale local media remains available for comparison preview', () => {
  const stale = {
    image_status: 'stale',
    audio_status: 'completed',
    image_url: '/media/old.png',
    audio_url: '/media/ready.wav',
  }

  assert.equal(isSegmentPreviewReady(stale), true)
  assert.equal(areAllSegmentAssetsReady([stale]), false)
})

test('backend stale recovery is the only primary recovery action even outside failed stages', () => {
  const controls = deriveWorkspaceControls({
    stage: 'ready',
    segments: [],
    recovery: {
      allowed: true,
      mode: 'update_stale_assets',
      label: '更新 1 个受影响素材',
      description: '旧素材仍可查看',
    },
  })

  assert.equal(controls.isRecoverable, true)
  assert.equal(controls.canResume, true)
  assert.equal(controls.recoveryLabel, '更新 1 个受影响素材')
})
