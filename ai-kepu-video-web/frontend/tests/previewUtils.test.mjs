import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendPromptGuidance,
  createTaskRequestGuard,
  getSegmentDraftSnapshot,
  getSegmentAssetState,
  isTaskLoadPending,
  normalizeSubtitleText,
  sortSegmentsByIndex,
} from '../src/pages/previewUtils.js'

test('sorts numeric segment indexes without removing failed assets', () => {
  const segments = sortSegmentsByIndex([
    { segment_index: '10', image_status: 'completed' },
    { segment_index: '2', image_status: 'failed', image_url: '/media/kept.png' },
  ])

  assert.deepEqual(segments.map((segment) => segment.segment_index), ['2', '10'])
  assert.equal(segments[0].image_url, '/media/kept.png')
})

test('reports failed and missing segment assets as editable recovery states', () => {
  assert.deepEqual(getSegmentAssetState({ image_status: 'failed', audio_url: '/media/audio.wav' }), {
    label: '图片失败',
    tone: 'danger',
  })
  assert.deepEqual(getSegmentAssetState({ image_url: '/media/image.png' }), {
    label: '素材缺失',
    tone: 'warning',
  })
})

test('trims subtitle punctuation and appends prompt guidance only once', () => {
  assert.equal(normalizeSubtitleText('  ，，这是字幕。  '), '这是字幕')

  const first = appendPromptGuidance('人物在书桌前讲解')
  assert.match(first, /字幕安全区/u)
  assert.equal(appendPromptGuidance(first), first)
})

test('creates a new draft snapshot when the task changes with the same segment index', () => {
  const taskADraft = getSegmentDraftSnapshot('task-a', {
    id: 'segment-a-0',
    segment_index: 0,
    text: '任务 A 的字幕',
    image_prompt: '任务 A 的提示词',
  })
  const taskBDraft = getSegmentDraftSnapshot('task-b', {
    id: 'segment-b-0',
    segment_index: 0,
    text: '任务 B 的字幕',
    image_prompt: '任务 B 的提示词',
  })

  assert.notEqual(taskADraft.key, taskBDraft.key)
  assert.deepEqual(taskBDraft, {
    key: 'task-b:segment-b-0:0:任务 B 的字幕:任务 B 的提示词',
    text: '任务 B 的字幕',
    imagePrompt: '任务 B 的提示词',
  })
})

test('stops holding the editor in a loading state after the current task fails to load', () => {
  assert.equal(isTaskLoadPending({
    loading: false,
    loadError: '任务读取失败',
    loadedTaskId: null,
    taskId: 'task-b',
  }), false)
})

test('rejects a deferred task A completion after the route transitions to task B', async () => {
  let resolveRequest
  const request = new Promise(resolve => { resolveRequest = resolve })
  const guard = createTaskRequestGuard('task-a')
  const requestToken = guard.begin('task-a')
  const completion = request.then(result => (guard.accepts(requestToken) ? result : null))

  guard.changeTask('task-b')
  resolveRequest({ image_url: '/media/task-a.png' })

  assert.equal(await completion, null)
})
