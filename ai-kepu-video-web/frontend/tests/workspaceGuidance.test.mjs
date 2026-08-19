import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildFailedRetryPayload,
  collectWorkspaceIssues,
  deriveWorkspaceJourney,
  partitionWorkspaceFailures,
  resolveWorkspaceStep,
  segmentFailureTargets,
} from '../src/pages/workspaceGuidance.js'

test('every legal workspace phase resolves to one stable journey step', () => {
  const cases = [
    [{ stage: 'planning', planning_step: 'text_generation' }, 1],
    [{ stage: 'planning', planning_step: 'segmentation' }, 1],
    [{ stage: 'planning', planning_step: 'image_prompt_generation' }, 1],
    [{ stage: 'awaiting_confirmation', voice_confirmed: false }, 2],
    [{ stage: 'awaiting_confirmation', voice_confirmed: true, voice_type: 'mimo:default' }, 3],
    [{ stage: 'generating_assets' }, 4],
    [{ stage: 'repairing_assets' }, 4],
    [{ stage: 'awaiting_finalization' }, 5],
    [{ stage: 'finalizing' }, 5],
    [{ stage: 'ready' }, 5],
    [{ stage: 'interrupted', recovery: { mode: 'resume_planning' } }, 1],
    [{ stage: 'failed', recovery: { mode: 'retry_assets' } }, 4],
    [{ stage: 'failed', recovery: { mode: 'finalize_failed' } }, 5],
    [{ stage: 'interrupted', active_operation: { status: 'running', kind: 'retry_assets' } }, 4],
    [{ stage: 'interrupted', active_operation: { status: 'running', kind: 'finalize' } }, 5],
  ]

  cases.forEach(([workspace, expected]) => assert.equal(resolveWorkspaceStep(workspace), expected))
})

test('zero, one-segment, and malformed legacy progress stays finite and bounded', () => {
  const workspaces = [
    { stage: 'planning', segments_count: 0, progress: {} },
    { stage: 'generating_assets', segments_count: 1, progress: { images_ready: 1, audio_ready: 0 } },
    { stage: 'repairing_assets', segments_count: 'legacy', progress: { images_ready: -4, audio_ready: Number.NaN } },
    { stage: 'finalizing', active_operation: { kind: 'finalize', status: 'running', total: 0, completed: 9 } },
  ]

  workspaces.forEach(workspace => {
    const journey = deriveWorkspaceJourney(workspace)
    assert.equal(Number.isFinite(journey.percent), true)
    assert.equal(journey.percent >= 0 && journey.percent <= 100, true)
    assert.equal(journey.steps.filter(step => step.state === 'current').length, 1)
  })
})

test('repair keeps completed earlier steps while ready reaches 100 percent', () => {
  const repairing = deriveWorkspaceJourney({
    stage: 'repairing_assets',
    segments_count: 2,
    progress: { images_ready: 1, audio_ready: 2 },
  })
  const ready = deriveWorkspaceJourney({ stage: 'ready' })

  assert.deepEqual(repairing.steps.slice(0, 4).map(step => step.state), ['completed', 'completed', 'completed', 'completed'])
  assert.equal(repairing.steps[4].state, 'current')
  assert.equal(ready.percent, 100)
  assert.equal(ready.steps.every(step => step.state === 'completed'), true)
})

test('failures are unique per target, include multiple types per segment, and exclude stale', () => {
  const first = {
    segment_index: 3,
    prompt_status: 'failed',
    prompt_error_code: 'timeout',
    image_status: 'failed',
    image_error_code: 'rate_limit',
    audio_status: 'stale',
  }
  const issues = collectWorkspaceIssues({
    segments: [
      first,
      { segment_index: 8, prompt_status: 'completed', image_status: 'completed', audio_status: 'failed', audio_error_code: 'auth' },
    ],
    recovery: {
      targets: [
        { segment_index: 3, asset_type: 'image', status: 'failed' },
        { segment_index: 3, asset_type: 'image', status: 'failed' },
      ],
    },
  })

  assert.deepEqual(segmentFailureTargets(first).map(target => target.assetType), ['prompt', 'image'])
  assert.equal(issues.failureCount, 3)
  assert.equal(issues.failedSegmentCount, 2)
  assert.deepEqual(issues.counts, { prompt: 1, image: 1, audio: 1 })
  assert.deepEqual(issues.stale.map(target => target.key), ['3:audio'])
  assert.equal(new Set(issues.failures.map(target => target.key)).size, issues.failureCount)
})

test('batch failure retry always delegates scope resolution to the backend and never sends stale targets', () => {
  assert.deepEqual(buildFailedRetryPayload({
    snapshot_key: 'snapshot-v4',
    recovery: { targets: [{ segment_index: 2, asset_type: 'image', status: 'stale' }] },
  }), {
    snapshot_key: 'snapshot-v4',
    scope: 'failed',
  })
})

test('batch material repair excludes prompt failures, which remain precise segment actions', () => {
  const issues = collectWorkspaceIssues({
    segments: [
      { segment_index: 2, prompt_status: 'failed', image_status: 'pending', audio_status: 'completed' },
      { segment_index: 3, prompt_status: 'completed', image_status: 'failed', audio_status: 'failed' },
    ],
  })
  const partitioned = partitionWorkspaceFailures(issues)

  assert.deepEqual(partitioned.prompts.map(target => target.key), ['2:prompt'])
  assert.deepEqual(partitioned.assets.map(target => target.key), ['3:image', '3:audio'])
  assert.equal(partitioned.assets.some(target => target.assetType === 'prompt'), false)
})
