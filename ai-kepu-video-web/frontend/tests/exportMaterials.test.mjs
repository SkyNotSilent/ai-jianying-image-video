import test from 'node:test'
import assert from 'node:assert/strict'

import { materialPackageSummary, resolveApiDownloadUrl } from '../src/pages/exportMaterials.js'


test('resolves material downloads against the backend base URL', () => {
  assert.equal(
    resolveApiDownloadUrl('http://localhost:2002/', '/ai/native/video/kepu/tasks/task-1/download-materials?snapshot_key=abc'),
    'http://localhost:2002/ai/native/video/kepu/tasks/task-1/download-materials?snapshot_key=abc',
  )
  assert.equal(
    resolveApiDownloadUrl('http://localhost:2002', 'https://example.test/materials.zip'),
    'https://example.test/materials.zip',
  )
})


test('describes a complete current material package', () => {
  assert.deepEqual(materialPackageSummary({
    available: true,
    complete: true,
    segment_count: 12,
    image_count: 12,
    audio_count: 12,
    missing_image_orders: [],
    missing_audio_orders: [],
  }), {
    available: true,
    complete: true,
    detail: '12 张图片 · 12 段音频 · 12 个分镜',
    statusLabel: '素材完整',
    warning: '',
  })
})


test('keeps a partial package downloadable and reports missing assets', () => {
  const summary = materialPackageSummary({
    available: true,
    complete: false,
    segment_count: 5,
    image_count: 4,
    audio_count: 3,
    missing_image_orders: [2],
    missing_audio_orders: [2, 5],
  })

  assert.equal(summary.available, true)
  assert.equal(summary.statusLabel, '部分素材')
  assert.equal(summary.warning, '缺少 1 张图片、缺少 2 段音频，将下载当前已有素材。')
})


test('disables material delivery when no current file exists', () => {
  const summary = materialPackageSummary({
    available: false,
    segment_count: 3,
    image_count: 0,
    audio_count: 0,
  })

  assert.equal(summary.available, false)
  assert.equal(summary.statusLabel, '暂无素材')
})
