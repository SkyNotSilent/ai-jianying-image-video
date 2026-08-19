import assert from 'node:assert/strict'
import test from 'node:test'

import {
  readWorkspaceView,
  workspaceViewKey,
  writeWorkspaceView,
} from '../src/pages/workspaceViewState.js'

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    snapshot: () => Object.fromEntries(values),
  }
}

test('workspace view restores selection, active mobile pane, inspector tab, and all scroll regions', () => {
  const storage = memoryStorage()
  writeWorkspaceView('project-a', {
    selectedIndex: 8,
    mobilePane: 'storyboard',
    settingsOpen: true,
    scroll: { storyboard: 420, preview: 735, segmentInspector: 116, fullSettings: 268 },
  }, storage)

  assert.deepEqual(readWorkspaceView('project-a', storage), {
    selectedIndex: 8,
    mobilePane: 'storyboard',
    settingsOpen: true,
    scroll: { storyboard: 420, preview: 735, segmentInspector: 116, fullSettings: 268 },
  })
})

test('partial scroll updates merge without resetting other panes or selection', () => {
  const storage = memoryStorage()
  writeWorkspaceView('project-b', { selectedIndex: 4, scroll: { preview: 300, storyboard: 90 } }, storage)
  writeWorkspaceView('project-b', { scroll: { preview: 640 } }, storage)

  const restored = readWorkspaceView('project-b', storage)
  assert.equal(restored.selectedIndex, 4)
  assert.equal(restored.scroll.preview, 640)
  assert.equal(restored.scroll.storyboard, 90)
})

test('malformed or unavailable storage falls back safely and retains the legacy selection key', () => {
  const taskId = 'legacy'
  const storage = memoryStorage({
    [`insightcut:selected:${taskId}`]: '3',
    [workspaceViewKey(taskId)]: '{broken',
  })
  assert.equal(readWorkspaceView(taskId, storage).selectedIndex, 3)

  const legacyOnly = memoryStorage({ [`insightcut:selected:${taskId}`]: '3' })
  assert.equal(readWorkspaceView(taskId, legacyOnly).selectedIndex, 3)

  const throwing = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } }
  assert.doesNotThrow(() => writeWorkspaceView(taskId, { selectedIndex: 2 }, throwing))
  assert.equal(readWorkspaceView(taskId, throwing).selectedIndex, 0)
})
