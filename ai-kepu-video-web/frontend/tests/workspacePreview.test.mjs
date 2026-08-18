import test from 'node:test'
import assert from 'node:assert/strict'

import {
  areAllSegmentAssetsReady,
  isSegmentPreviewReady,
  nextPreviewIndex,
  previewPlaybackStartIndex,
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
