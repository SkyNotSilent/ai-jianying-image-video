const VIEW_KEY_PREFIX = 'insightcut:workspace-view:'
const LEGACY_SELECTED_PREFIX = 'insightcut:selected:'
const MOBILE_PANES = new Set(['storyboard', 'preview', 'settings'])
const SCROLL_PANES = ['storyboard', 'preview', 'segmentInspector', 'fullSettings']

function availableStorage(storage) {
  if (storage) return storage
  try { return globalThis.localStorage }
  catch { return null }
}

function nonNegativeInteger(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : fallback
}

function normalizeScroll(value = {}) {
  return Object.fromEntries(SCROLL_PANES.map(pane => [pane, nonNegativeInteger(value?.[pane])]))
}

function normalizeWorkspaceView(value = {}, legacySelected = 0) {
  return {
    selectedIndex: nonNegativeInteger(value.selectedIndex, nonNegativeInteger(legacySelected)),
    mobilePane: MOBILE_PANES.has(value.mobilePane) ? value.mobilePane : 'preview',
    settingsOpen: typeof value.settingsOpen === 'boolean' ? value.settingsOpen : false,
    scroll: normalizeScroll(value.scroll),
  }
}

export function workspaceViewKey(taskId) {
  return `${VIEW_KEY_PREFIX}${taskId}`
}

export function readWorkspaceView(taskId, storage) {
  const target = availableStorage(storage)
  if (!target) return normalizeWorkspaceView()
  let legacySelected = 0
  try {
    legacySelected = target.getItem(`${LEGACY_SELECTED_PREFIX}${taskId}`)
  } catch {
    return normalizeWorkspaceView()
  }
  try {
    const parsed = JSON.parse(target.getItem(workspaceViewKey(taskId)) || '{}')
    return normalizeWorkspaceView(parsed && typeof parsed === 'object' ? parsed : {}, legacySelected)
  } catch {
    return normalizeWorkspaceView({}, legacySelected)
  }
}

export function writeWorkspaceView(taskId, patch, storage) {
  const target = availableStorage(storage)
  const current = readWorkspaceView(taskId, target)
  const next = normalizeWorkspaceView({
    ...current,
    ...patch,
    scroll: { ...current.scroll, ...(patch?.scroll || {}) },
  }, current.selectedIndex)
  if (!target) return next
  try {
    target.setItem(workspaceViewKey(taskId), JSON.stringify(next))
    // Keep the old key during the compatibility window for already-open clients.
    target.setItem(`${LEGACY_SELECTED_PREFIX}${taskId}`, String(next.selectedIndex))
  } catch { /* View persistence must never block editing. */ }
  return next
}

export const WORKSPACE_SCROLL_PANES = Object.freeze([...SCROLL_PANES])
