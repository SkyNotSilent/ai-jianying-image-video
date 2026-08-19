import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const routedSurfaces = [
  '../src/App.jsx',
  '../src/components/BrandNavigation.jsx',
  '../src/components/PollingFailureNotice.jsx',
  '../src/components/StatusStates.jsx',
  '../src/components/WorkspaceFailureBanner.jsx',
  '../src/components/WorkspaceStageNavigator.jsx',
  '../src/pages/ManuscriptPage.jsx',
  '../src/pages/WorkspacePage.jsx',
  '../src/pages/ProjectAssetsPage.jsx',
  '../src/pages/SettingsPage.jsx',
  '../src/pages/ExportPage.jsx',
]

function visibleStrings(source) {
  const values = []
  const patterns = [
    />([^<>{}\n][^<>{}]*)</g,
    /\b(?:title|label|description|placeholder|message|fallback|aria-label)=(?:"([^"]*)"|'([^']*)')/g,
    /\btoast\.(?:success|warning|error|info)\((?:'([^']*)'|"([^"]*)"|`([^`]*)`)/g,
  ]
  patterns.forEach(pattern => {
    for (const match of source.matchAll(pattern)) values.push(match.slice(1).find(Boolean) || '')
  })
  return values.join('\n')
}

test('main product surfaces use the approved terminology', () => {
  const visible = routedSurfaces.map(path => visibleStrings(readFileSync(new URL(path, import.meta.url), 'utf8'))).join('\n')
  for (const forbidden of ['生产预案', '内容预案', '高保真', '视频任务', '项目任务', '任务总进度']) {
    assert.doesNotMatch(visible, new RegExp(forbidden), `用户可见文案仍包含禁用词：${forbidden}`)
  }
})
