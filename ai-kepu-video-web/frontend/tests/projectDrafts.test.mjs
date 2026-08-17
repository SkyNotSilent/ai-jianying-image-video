import assert from 'node:assert/strict'
import test from 'node:test'

import { createDraft, getLatestDraft, saveDraft } from '../src/utils/projectDrafts.js'

function memoryStorage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  }
}

test('keeps the most recently edited manuscript available when returning to the root page', () => {
  globalThis.window = { localStorage: memoryStorage() }
  const first = createDraft({ name: '第一版', manuscript: '会被保留的文稿' })
  const second = createDraft({ name: '第二版' })
  saveDraft({ ...first, manuscript: '从设置页返回后仍然存在' })

  assert.notEqual(first.draft_id, second.draft_id)
  assert.equal(getLatestDraft().draft_id, first.draft_id)
  assert.equal(getLatestDraft().manuscript, '从设置页返回后仍然存在')
})
