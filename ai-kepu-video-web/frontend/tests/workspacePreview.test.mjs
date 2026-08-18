import test from 'node:test'
import assert from 'node:assert/strict'

import { isSegmentPreviewReady, nextPreviewIndex } from '../src/pages/workspacePreview.js'

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
