import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendPromptGuidance,
  getSegmentAssetState,
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
